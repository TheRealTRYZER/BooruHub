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
from app.core.security import encrypt_key, decrypt_key

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


def _credential_usable(ciphertext: Optional[str], login: Optional[str], env_login: str, env_key: str) -> bool:
    """Return True when this site can actually authenticate.

    Reporting `bool(ciphertext)` was wrong: a key encrypted under a previous
    ENCRYPTION_KEY still exists in the database, so the UI showed a green tick
    while every request went out unauthenticated. This mirrors the pair
    get_auth_params() in BaseBooru needs (login + decryptable key), and treats
    the global .env credentials as a usable fallback.
    """
    if env_login.strip() and env_key.strip():
        return True
    if not ciphertext or not (login or "").strip():
        return False
    return bool(decrypt_key(ciphertext))


@router.get("/keys/status")
async def get_keys_status(user: User = Depends(require_user)):
    """Return which API keys are configured (without revealing values)."""
    settings = get_settings()

    danbooru = _credential_usable(
        user.danbooru_api_key, user.danbooru_login,
        settings.DANBOORU_LOGIN, settings.DANBOORU_API_KEY,
    )
    e621 = _credential_usable(
        user.e621_api_key, user.e621_login,
        settings.E621_LOGIN, settings.E621_API_KEY,
    )
    rule34 = _credential_usable(
        user.rule34_api_key, user.rule34_user_id,
        settings.RULE34_USER_ID, settings.RULE34_API_KEY,
    )

    # A stored key that can no longer be decrypted is worth calling out: it
    # only happens after ENCRYPTION_KEY is rotated, and the fix is to re-enter
    # the key.
    unreadable = [
        site for site, stored, usable in (
            ("danbooru", bool(user.danbooru_api_key), danbooru),
            ("e621", bool(user.e621_api_key), e621),
            ("rule34", bool(user.rule34_api_key), rule34),
        ) if stored and not usable
    ]

    return {
        "danbooru": danbooru,
        "danbooru_login": user.danbooru_login or "",
        "e621": e621,
        "e621_login": user.e621_login or "",
        "rule34": rule34,
        "rule34_user_id": user.rule34_user_id or "",
        "unreadable": unreadable,
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
