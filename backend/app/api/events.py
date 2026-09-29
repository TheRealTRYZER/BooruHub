"""Events API — user event logging for the recommendation system."""
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete, func, select

from app.db.database import get_db
from app.db.models import User, UserEvent
from app.api.deps import require_user
from app.core.rate_limit import rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/events", tags=["events"])

ALLOWED_TYPES = {"impression", "view", "like", "favourite", "search"}

MAX_EVENTS_PER_BATCH = 50
MAX_TAGS = 100
MAX_TAG_LENGTH = 255
# Ceiling on stored events per user. Events are append-only and the write path
# is rate limited per IP, which a forged X-Forwarded-For could previously
# bypass, so the table needed a hard bound of its own.
MAX_EVENTS_PER_USER = 50_000


class EventPayload(BaseModel):
    # Lengths mirror the column widths in app/db/models.py. A value wider than
    # its column raised a DataError and the whole batch was discarded.
    type: str = Field(..., max_length=16)
    source: Optional[str] = Field(None, max_length=32)
    post_id: Optional[str] = Field(None, max_length=50)
    tags: Optional[List[str]] = Field(None, max_length=MAX_TAGS)
    query: Optional[str] = Field(None, max_length=512)
    duration_sec: Optional[int] = Field(None, ge=0)

    @field_validator("tags")
    @classmethod
    def tags_bounded(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is None:
            return None
        return [t[:MAX_TAG_LENGTH] for t in v]


class BatchEventsRequest(BaseModel):
    events: List[EventPayload] = Field(..., max_length=MAX_EVENTS_PER_BATCH)


class EventCountResponse(BaseModel):
    total: int


class DeleteHistoryResponse(BaseModel):
    deleted: int


@router.post("/batch", status_code=status.HTTP_202_ACCEPTED)
async def log_events_batch(
    req: BatchEventsRequest,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
    _rl=Depends(rate_limit("events", max_requests=30, window_seconds=60)),
):
    """Log a batch of user events. Fire-and-forget from frontend.
    Only logs if user has given data_consent.
    """
    if not user.data_consent:
        return {"accepted": 0, "reason": "no_consent"}

    accepted = 0
    for ev in req.events:
        ev_type = ev.type.lower()
        if ev_type == "favorite":
            ev_type = "favourite"
            
        if ev_type not in ALLOWED_TYPES:
            continue

        event = UserEvent(
            user_id=user.id,
            type=ev_type,
            source=ev.source,
            post_id=ev.post_id,
            tags=ev.tags,
            query=ev.query,
            duration_sec=ev.duration_sec,
        )
        db.add(event)
        accepted += 1

    if accepted > 0:
        try:
            await db.commit()
            # Trim the oldest rows so one user cannot grow the table without
            # bound. Single statement, runs only on the write path.
            await db.execute(
                delete(UserEvent).where(
                    UserEvent.id.in_(
                        select(UserEvent.id)
                        .where(UserEvent.user_id == user.id)
                        .order_by(UserEvent.ts.desc(), UserEvent.id.desc())
                        .limit(MAX_EVENTS_PER_USER)
                        .offset(MAX_EVENTS_PER_USER)
                    )
                )
            )
            await db.commit()
        except Exception as e:
            logger.error(f"Failed to log events: {e}")
            await db.rollback()
            return {"accepted": 0}

    return {"accepted": accepted}


@router.get("/count", response_model=EventCountResponse)
async def get_event_count(
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """Get total event count for the current user."""
    result = await db.execute(
        select(func.count(UserEvent.id)).where(UserEvent.user_id == user.id)
    )
    total = result.scalar_one()
    return {"total": total}


@router.delete("/history", response_model=DeleteHistoryResponse)
async def delete_history(
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """GDPR: Delete all event history for the current user."""
    # B-M12: Use SELECT count(*) before delete for reliable rowcount
    count_stmt = select(func.count(UserEvent.id)).where(UserEvent.user_id == user.id)
    result = await db.execute(count_stmt)
    deleted = result.scalar_one()

    await db.execute(
        delete(UserEvent).where(UserEvent.user_id == user.id)
    )
    await db.commit()
    logger.info(f"[GDPR] User {user.id} deleted {deleted} events")
    return {"deleted": deleted}
