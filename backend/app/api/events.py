"""Events API — user event logging for the recommendation system."""
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete, func, select

from app.db.database import get_db
from app.db.models import User, UserEvent
from app.api.deps import require_user
from app.core.rate_limit import rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/events", tags=["events"])

ALLOWED_TYPES = {"impression", "view", "like", "favourite", "search"}


class EventPayload(BaseModel):
    type: str = Field(..., max_length=50, description="Event type: impression, view, like, favourite, search")
    source: Optional[str] = Field(None, max_length=100)
    post_id: Optional[str] = Field(None, max_length=100)
    tags: Optional[List[str]] = Field(None, max_length=100)
    query: Optional[str] = Field(None, max_length=512)
    duration_sec: Optional[int] = Field(None, ge=0)


class BatchEventsRequest(BaseModel):
    events: List[EventPayload] = Field(..., max_length=50)


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
