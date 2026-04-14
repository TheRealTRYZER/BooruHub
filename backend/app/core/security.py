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
    """Legacy 32-byte padding for backward compatibility."""
    key = secret.encode()
    if len(key) < 32:
        key = key.ljust(32, b"0")
    return base64.urlsafe_b64encode(key[:32])


def _derive_fernet_key_secure(secret: str) -> bytes:
    """Secure derivation using PBKDF2."""
    # We use a static salt because this is derived from a global secret (JWT_SECRET)
    # for system-wide encryption of user API keys.
    salt = b"booruhub_crypto_salt_2024" 
    key = hashlib.pbkdf2_hmac('sha256', secret.encode(), salt, 100000)
    return base64.urlsafe_b64encode(key)


def _get_fernets():
    settings = get_settings()
    key_source = settings.ENCRYPTION_KEY or settings.JWT_SECRET
    secure_f = Fernet(_derive_fernet_key_secure(key_source))
    legacy_f = Fernet(_derive_fernet_key(key_source))
    return secure_f, legacy_f


# --------------- API-key encryption ---------------

def encrypt_key(plain_text: str) -> str:
    """Encrypt an API key for storage in the database using the secure key."""
    if not plain_text:
        return ""
    secure_f, _ = _get_fernets()
    return secure_f.encrypt(plain_text.encode()).decode()


def decrypt_key(encrypted_text: str) -> str:
    """Decrypt an API key, trying the secure key first, then falling back to legacy."""
    if not encrypted_text:
        return ""
    
    secure_f, legacy_f = _get_fernets()
    encoded_text = encrypted_text.encode()

    # 1. Try secure key
    try:
        return secure_f.decrypt(encoded_text).decode()
    except InvalidToken:
        pass
    
    # 2. Try legacy fallback
    try:
        return legacy_f.decrypt(encoded_text).decode()
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
