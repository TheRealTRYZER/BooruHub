"""JWT, password hashing, and API-key encryption utilities."""
import base64
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def _derive_fernet_key(secret: str) -> bytes:
    """Legacy 32-byte padding for backward compatibility with existing DB keys."""
    key = secret.encode()
    if len(key) < 32:
        key = key.ljust(32, b"0")
    return base64.urlsafe_b64encode(key[:32])


def _get_fernet() -> Fernet:
    settings = get_settings()
    # Prefer dedicated ENCRYPTION_KEY if set, else derive from JWT_SECRET
    key_source = settings.ENCRYPTION_KEY or settings.JWT_SECRET
    return Fernet(_derive_fernet_key(key_source))


# --------------- API-key encryption ---------------

def encrypt_key(plain_text: str) -> str:
    """Encrypt an API key for storage in the database."""
    if not plain_text:
        return ""
    return _get_fernet().encrypt(plain_text.encode()).decode()


def decrypt_key(encrypted_text: str) -> str:
    """Decrypt an API key retrieved from the database."""
    if not encrypted_text:
        return ""
    try:
        return _get_fernet().decrypt(encrypted_text.encode()).decode()
    except InvalidToken:
        logger.warning("Failed to decrypt API key — token invalid or key rotated")
        return ""


# --------------- Passwords ---------------

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


# --------------- JWT ---------------

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    settings = get_settings()
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    )
    to_encode["exp"] = expire
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    settings = get_settings()
    try:
        return jwt.decode(
            token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
        )
    except jwt.PyJWTError:
        return None
