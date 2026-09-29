"""User settings API — manage API keys, profile, and search preferences."""
import logging
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.core.config import get_settings
from app.db.models import User
from app.api.deps import require_user
from app.core.security import encrypt_key

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/user", tags=["user"])


class ApiSettingsUpdate(BaseModel):
    # Login columns are String(255); wider values raised a DataError.
    danbooru_login: Optional[str] = Field(default=None, max_length=255)
    danbooru_api_key: Optional[str] = Field(default=None, max_length=255)
    e621_login: Optional[str] = Field(default=None, max_length=255)
    e621_api_key: Optional[str] = Field(default=None, max_length=255)
    rule34_user_id: Optional[str] = Field(default=None, max_length=255)
    rule34_api_key: Optional[str] = Field(default=None, max_length=512)
    search_limit: Optional[int] = Field(default=None, ge=1, le=200)
    search_timeout: Optional[float] = Field(default=None, ge=1.0, le=120.0)
    search_interval: Optional[float] = Field(default=None, ge=0.0, le=60.0)


@router.put("/keys")
async def update_settings(
    body: ApiSettingsUpdate,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    # Danbooru
    if body.danbooru_login is not None:
        user.danbooru_login = body.danbooru_login
    if body.danbooru_api_key is not None:
        # An empty value clears the stored key. The old `if body.x_api_key:`
        # check ignored falsy values, so a key could be set but never removed.
        user.danbooru_api_key = encrypt_key(body.danbooru_api_key) if body.danbooru_api_key else None

    # e621
    if body.e621_login is not None:
        user.e621_login = body.e621_login
    if body.e621_api_key is not None:
        user.e621_api_key = encrypt_key(body.e621_api_key) if body.e621_api_key else None

    # Rule34
    if body.rule34_user_id is not None:
        user.rule34_user_id = body.rule34_user_id
    if body.rule34_api_key is not None:
        val = body.rule34_api_key.strip()
        if not val:
            user.rule34_api_key = None
        elif "api_key=" in val or "user_id=" in val:
            import urllib.parse
            # Parse query-string format like "&api_key=abc&user_id=123"
            parsed = urllib.parse.parse_qs(val.lstrip('&?'))
            if 'api_key' in parsed:
                user.rule34_api_key = encrypt_key(parsed['api_key'][0])
            if 'user_id' in parsed:
                user.rule34_user_id = parsed['user_id'][0]
        else:
            user.rule34_api_key = encrypt_key(val)

    # Search preferences
    if body.search_limit is not None:
        user.search_limit = max(1, min(body.search_limit, 200))
    if body.search_timeout is not None:
        user.search_timeout = max(1.0, min(body.search_timeout, 120.0))
    if body.search_interval is not None:
        user.search_interval = max(0.0, min(body.search_interval, 60.0))

    await db.commit()
    await db.refresh(user)
    logger.info(f"Settings updated for user {user.id}")
    return {"message": "Settings updated"}


@router.get("/keys/status")
async def get_keys_status(user: User = Depends(require_user)):
    """Return which API keys are configured (without revealing values)."""
    return {
        "danbooru": bool(user.danbooru_api_key),
        "danbooru_login": user.danbooru_login or "",
        "e621": bool(user.e621_api_key),
        "e621_login": user.e621_login or "",
        "rule34": bool(user.rule34_api_key),
        "rule34_user_id": user.rule34_user_id or "",
        "search_limit": user.search_limit,
        "search_timeout": user.search_timeout,
        "search_interval": user.search_interval,
        "data_consent": user.data_consent,
    }


class ConsentUpdate(BaseModel):
    data_consent: bool


@router.put("/consent")
async def update_consent(
    body: ConsentUpdate,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """Toggle data collection consent."""
    user.data_consent = body.data_consent
    await db.commit()
    logger.info(f"User {user.id} consent set to {body.data_consent}")
    return {"data_consent": user.data_consent}
