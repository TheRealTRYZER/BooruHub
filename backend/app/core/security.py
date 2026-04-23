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
    salt = b"booruhub_crypto_salt_2024"
    key = hashlib.pbkdf2_hmac("sha256", secret.encode(), salt, 100000)
    return base64.urlsafe_b64encode(key)


def _is_fernet_key(value: str) -> bool:
    try:
        return len(base64.urlsafe_b64decode(value.encode())) == 32
    except Exception:
        return False


def _build_fernet_variants(secret: str) -> list[Fernet]:
    variants = [Fernet(_derive_fernet_key_secure(secret)), Fernet(_derive_fernet_key(secret))]
    if _is_fernet_key(secret):
        variants.insert(0, Fernet(secret.encode()))
    return variants


def _get_encryption_fernets() -> list[Fernet]:
    settings = get_settings()
    key_sources: list[str] = []

    if settings.ENCRYPTION_KEY:
        key_sources.append(settings.ENCRYPTION_KEY)
    if settings.JWT_SECRET:
        key_sources.append(settings.JWT_SECRET)
    key_sources.extend(settings.encryption_key_fallback_list)

    seen: set[str] = set()
    fernets: list[Fernet] = []
    for source in key_sources:
        if source in seen:
            continue
        seen.add(source)
        fernets.extend(_build_fernet_variants(source))
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
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


_REFRESH_EXPIRE_DAYS = 30


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    settings = get_settings()
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    )
    to_encode["exp"] = expire
    to_encode["type"] = "access"
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
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
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_refresh_token(token: str) -> Optional[dict]:
    """Decode and validate a refresh token. Returns None if invalid or wrong type."""
    settings = get_settings()
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
        )
        if payload.get("type") != "refresh":
            return None
        return payload
    except jwt.PyJWTError:
        return None
