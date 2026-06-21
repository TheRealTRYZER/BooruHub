"""JWT, password hashing, and API-key encryption utilities."""
import base64
import hashlib
import hmac
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def is_fernet_key(value: str) -> bool:
    """Check if the provided string is a valid 32-byte urlsafe-base64 key."""
    try:
        return len(base64.urlsafe_b64decode(value.encode())) == 32
    except Exception:
        return False


def _get_encryption_fernets() -> list[Fernet]:
    settings = get_settings()
    key_sources: list[str] = []

    if settings.ENCRYPTION_KEY:
        key_sources.append(settings.ENCRYPTION_KEY)
    key_sources.extend(settings.encryption_key_fallback_list)

    seen: set[str] = set()
    fernets: list[Fernet] = []
    for source in key_sources:
        if source in seen:
            continue
        seen.add(source)
        if is_fernet_key(source):
            fernets.append(Fernet(source.encode()))
    return fernets


def encrypt_key(plain_text: str) -> str:
    """Encrypt an API key for storage in the database using the primary key."""
    if not plain_text:
        return ""
    fernets = _get_encryption_fernets()
    if not fernets:
        raise RuntimeError("Encryption is not configured")
    return fernets[0].encrypt(plain_text.encode()).decode()


def decrypt_key(encrypted_text: str) -> str:
    """Decrypt an API key, trying active and fallback encryption keys."""
    if not encrypted_text:
        return ""

    encoded_text = encrypted_text.encode()
    for fernet in _get_encryption_fernets():
        try:
            return fernet.decrypt(encoded_text).decode()
        except InvalidToken:
            continue

    logger.warning("Failed to decrypt API key: token invalid or no configured key matched")
    return ""


def hash_password(password: str) -> str:
    """Hash password pre-hashed with SHA-256 to avoid bcrypt 72-byte truncation.
    
    DEPRECATED: Pre-hashing with SHA-256 before bcrypt is deprecated and kept for backward compatibility.
    """
    pre_hashed = hashlib.sha256(password.encode()).hexdigest()
    return bcrypt.hashpw(pre_hashed.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    """Verify password with SHA-256 pre-hashing and legacy fallback support.
    
    DEPRECATED: Legacy pre-hashed format verification, kept for backward compatibility.
    """
    pre_hashed = hashlib.sha256(password.encode()).hexdigest()
    try:
        if bcrypt.checkpw(pre_hashed.encode(), hashed.encode()):
            return True
    except ValueError:
        pass
    
    # Fallback to legacy verify without SHA-256 pre-hashing
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False


_REFRESH_EXPIRE_DAYS = 30


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    settings = get_settings()
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    )
    to_encode["exp"] = expire
    to_encode["type"] = "access"
    to_encode["iss"] = "booruhub"
    to_encode["aud"] = "booruhub_users"
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
            issuer="booruhub",
            audience="booruhub_users",
        )
        if payload.get("type") == "refresh":
            return None
        return payload
    except jwt.PyJWTError:
        return None


def create_refresh_token(data: dict) -> str:
    """Create a long-lived refresh token (30 days)."""
    settings = get_settings()
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=_REFRESH_EXPIRE_DAYS)
    to_encode["exp"] = expire
    to_encode["type"] = "refresh"
    to_encode["iss"] = "booruhub"
    to_encode["aud"] = "booruhub_users"
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_refresh_token(token: str) -> Optional[dict]:
    """Decode and validate a refresh token. Returns None if invalid or wrong type."""
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
            issuer="booruhub",
            audience="booruhub_users",
        )
        if payload.get("type") != "refresh":
            return None
        return payload
    except jwt.PyJWTError:
        return None


def hash_refresh_token(token: str) -> str:
    """Hash a refresh token using HMAC keyed by JWT_SECRET."""
    settings = get_settings()
    return hmac.new(
        settings.JWT_SECRET.encode(),
        token.encode(),
        hashlib.sha256
    ).hexdigest()
