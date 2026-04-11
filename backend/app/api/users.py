"""User settings API — manage API keys, profile, and search preferences."""
import logging
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models import User
from app.api.deps import require_user
from app.core.security import encrypt_key

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/user", tags=["user"])


class ApiSettingsUpdate(BaseModel):
    danbooru_login: Optional[str] = None
    danbooru_api_key: Optional[str] = None
    e621_login: Optional[str] = None
    e621_api_key: Optional[str] = None
    rule34_user_id: Optional[str] = None
    rule34_api_key: Optional[str] = None
    search_limit: Optional[int] = None
    search_timeout: Optional[float] = None
    search_interval: Optional[float] = None


@router.put("/keys")
async def update_settings(
    body: ApiSettingsUpdate,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    # Danbooru
    if body.danbooru_login is not None:
        user.danbooru_login = body.danbooru_login
    if body.danbooru_api_key:
        user.danbooru_api_key = encrypt_key(body.danbooru_api_key)

    # e621
    if body.e621_login is not None:
        user.e621_login = body.e621_login
    if body.e621_api_key:
        user.e621_api_key = encrypt_key(body.e621_api_key)

    # Rule34
    if body.rule34_user_id is not None:
        user.rule34_user_id = body.rule34_user_id
    if body.rule34_api_key:
        val = body.rule34_api_key.strip()
        if "api_key=" in val or "user_id=" in val:
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
        "search_interval": user.search_interval,
    }
