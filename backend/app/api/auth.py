import logging
from datetime import datetime, timezone, timedelta
import re
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func
from sqlalchemy.exc import IntegrityError

from app.db.database import get_db
from app.core.config import get_settings
from app.db.models import User, UserTagMapping, RefreshToken
from app.core.security import (
    hash_password_async, verify_password_async, dummy_verify_async, needs_rehash,
    create_access_token, create_refresh_token,
    decode_refresh_token, hash_refresh_token
)
from app.api.deps import require_user
from app.core.defaults import DEFAULT_USER_TAGS, STARTER_MAPPINGS
from app.core.rate_limit import rate_limit

router = APIRouter(prefix="/api/auth", tags=["auth"])
logger = logging.getLogger(__name__)


class AuthUserResponse(BaseModel):
    id: int
    username: str
    email: str
    default_tags: str


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    data_consent: bool = False

    @field_validator("username")
    @classmethod
    def username_alphanumeric(cls, v: str) -> str:
        # fullmatch, not re.match with a "$" anchor: "$" also matches just
        # before a trailing newline, so "admin\n" would slip through as a
        # distinct account.
        if not re.fullmatch(r"[a-zA-Z0-9_-]+", v):
            raise ValueError("Username may only contain letters, digits, underscores and hyphens")
        return v.lower()

    @field_validator("email")
    @classmethod
    def email_lowercase(cls, v: str) -> str:
        return v.lower()


class LoginRequest(BaseModel):
    login: str = Field(max_length=255, description="Username or email")
    password: str = Field(max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: AuthUserResponse


class RefreshRequest(BaseModel):
    refresh_token: Optional[str] = None


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    req: RegisterRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
    _rl=Depends(rate_limit("register", max_requests=3, window_seconds=60)),
):
    try:
        # Existing checks. The comparison has to fold case the same way login
        # does, otherwise "Admin" and "admin" are both accepted by the
        # case-sensitive unique index and the pair becomes an ambiguous login
        # that can no longer authenticate.
        existing_q = await db.execute(
            select(User).where(user_login_predicate(req.username))
        )
        if existing_q.scalars().first() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username or email already taken"
            )

        existing_q = await db.execute(
            select(User).where(user_login_predicate(req.email))
        )
        if existing_q.scalars().first() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username or email already taken"
            )

        # 1. Create User
        user = User(
            username=req.username,
            email=req.email,
            password_hash=await hash_password_async(req.password),
            default_tags=DEFAULT_USER_TAGS,
            data_consent=req.data_consent,
        )
        db.add(user)
        await db.flush()  # Get ID without committing whole transaction

        # 2. Add Starter Tag Mappings
        mappings = [
            UserTagMapping(
                user_id=user.id,
                unitag=m["unitag"],
                danbooru_tags=m["danbooru_tags"],
                e621_tags=m["e621_tags"],
                rule34_tags=m["rule34_tags"] or ""
            ) for m in STARTER_MAPPINGS
        ]
        db.add_all(mappings)
        
        token = create_access_token({"sub": str(user.id)})
        refresh = create_refresh_token({"sub": str(user.id)})

        db_refresh = RefreshToken(
            user_id=user.id,
            token_hash=hash_refresh_token(refresh),
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        db.add(db_refresh)

        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username or email already taken"
        )
    await db.refresh(user)

    settings = get_settings()
    response.set_cookie("access_token", token, httponly=True, secure=settings.COOKIE_SECURE, samesite=settings.COOKIE_SAMESITE, path="/")
    response.set_cookie("refresh_token", refresh, httponly=True, secure=settings.COOKIE_SECURE, samesite=settings.COOKIE_SAMESITE, path="/")

    return TokenResponse(
        access_token=token,
        refresh_token=refresh,
        user=AuthUserResponse(
            id=user.id, 
            username=user.username, 
            email=user.email, 
            default_tags=user.default_tags
        ),
    )



@router.post("/login", response_model=TokenResponse)
async def login(
    req: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
    _rl=Depends(rate_limit("login", max_requests=10, window_seconds=60)),
):
    result = await db.execute(select(User).where(user_login_predicate(req.login)))
    matches = result.scalars().all()

    if len(matches) > 1:
        # Rows that differ only by casing (written before username
        # normalisation) collide under the case-insensitive predicate. Which
        # account owns the password is unknowable, so fail closed instead of
        # letting scalar_one_or_none() raise and return a 500.
        logger.error(
            "Ambiguous login: %d accounts match login %r; refusing to authenticate",
            len(matches),
            req.login[:64],
        )
        await dummy_verify_async()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

    user = matches[0] if matches else None

    if not user:
        # Spend the same time as a real verification so response latency does
        # not reveal whether the account exists.
        await dummy_verify_async()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

    if not await verify_password_async(req.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

    # Upgrade legacy hashes (written before the sha256$ marker) on login.
    if needs_rehash(user.password_hash):
        user.password_hash = await hash_password_async(req.password)

    token = create_access_token({"sub": str(user.id)})
    refresh = create_refresh_token({"sub": str(user.id)})

    db_refresh = RefreshToken(
        user_id=user.id,
        token_hash=hash_refresh_token(refresh),
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
    )
    db.add(db_refresh)
    
    # B-M1: Clean up expired and old revoked tokens
    await db.execute(
        delete(RefreshToken).where(
            (RefreshToken.expires_at < datetime.now(timezone.utc)) |
            ((RefreshToken.revoked == True) & (RefreshToken.created_at < datetime.now(timezone.utc) - timedelta(days=30)))
        )
    )
    
    await db.commit()

    settings = get_settings()
    response.set_cookie("access_token", token, httponly=True, secure=settings.COOKIE_SECURE, samesite=settings.COOKIE_SAMESITE, path="/")
    response.set_cookie("refresh_token", refresh, httponly=True, secure=settings.COOKIE_SECURE, samesite=settings.COOKIE_SAMESITE, path="/")

    return TokenResponse(
        access_token=token,
        refresh_token=refresh,
        user=AuthUserResponse(
            id=user.id, 
            username=user.username, 
            email=user.email, 
            default_tags=user.default_tags
        ),
    )


def user_login_predicate(login: str):
    """Match an account by username or email, case-insensitively.

    Usernames and emails are stored lower-cased at registration, but rows
    written before that normalisation can still hold any casing. Comparing
    against the raw column would lock those accounts out of username login,
    so both sides are folded here.
    """
    folded = login.strip().lower()
    return (
        (func.lower(User.username) == folded) | (func.lower(User.email) == folded)
    )


async def _issue_refreshed_tokens(user: User, response: Response, db: AsyncSession) -> dict:
    """Mint and persist a new token pair for an already-authenticated user."""
    new_access = create_access_token({"sub": str(user.id)})
    new_refresh = create_refresh_token({"sub": str(user.id)})

    db.add(RefreshToken(
        user_id=user.id,
        token_hash=hash_refresh_token(new_refresh),
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
    ))

    # Clean up expired and long-revoked tokens
    await db.execute(
        delete(RefreshToken).where(
            (RefreshToken.expires_at < datetime.now(timezone.utc)) |
            ((RefreshToken.revoked == True) & (RefreshToken.created_at < datetime.now(timezone.utc) - timedelta(days=30)))
        )
    )

    try:
        await db.commit()
    except IntegrityError:
        # A jti collision is practically impossible, but never leak a 500.
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked refresh token",
        )

    settings = get_settings()
    response.set_cookie("access_token", new_access, httponly=True, secure=settings.COOKIE_SECURE, samesite=settings.COOKIE_SAMESITE, path="/")
    response.set_cookie("refresh_token", new_refresh, httponly=True, secure=settings.COOKIE_SECURE, samesite=settings.COOKIE_SAMESITE, path="/")

    return {
        "access_token": new_access,
        "refresh_token": new_refresh,
        "token_type": "bearer",
    }


@router.post("/refresh")
async def refresh_token(
    req: RefreshRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    _rl=Depends(rate_limit("refresh", max_requests=10, window_seconds=60)),
):
    """Exchange a valid refresh token for a new access token and new refresh token."""
    refresh_token_val = req.refresh_token or request.cookies.get("refresh_token")
    if not refresh_token_val:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )
        
    payload = decode_refresh_token(refresh_token_val)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    # Verify the refresh token in the database
    token_hash = hash_refresh_token(refresh_token_val)
    stmt = select(RefreshToken).where(
        RefreshToken.token_hash == token_hash,
    ).with_for_update()
    result = await db.execute(stmt)
    db_token = result.scalar_one_or_none()
    
    if not db_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked refresh token",
        )

    now = datetime.now(timezone.utc)
    if db_token.revoked:
        # A token revoked moments ago is usually two tabs racing to refresh
        # with the same cookie, not an attacker replaying a stolen token. Only
        # treat it as a replay once the grace window has passed.
        settings = get_settings()
        revoked_at = db_token.revoked_at
        within_grace = (
            revoked_at is not None
            and (now - revoked_at).total_seconds() <= settings.REFRESH_REUSE_GRACE_SECONDS
        )
        if within_grace:
            # The grace window only covers the rotation race, where the
            # replacement token was issued in the same call. A token the user
            # revoked deliberately through logout must stay dead: honouring
            # the window there would let a copy of the cookie restore a
            # session the user just ended.
            if db_token.revoked_by_logout:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or revoked refresh token",
                )
            result = await db.execute(select(User).where(User.id == int(user_id)))
            user = result.scalar_one_or_none()
            if user is None:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
            return await _issue_refreshed_tokens(user, response, db)

        # Genuine replay: revoke all tokens for this user. The logout marker is
        # cleared so these tokens fall under the strict replay path and can
        # never be revived by a later grace window.
        await db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == db_token.user_id)
            .values(revoked=True, revoked_at=now, revoked_by_logout=False)
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked refresh token",
        )

    if db_token.expires_at < now:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked refresh token",
        )

    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    # Mark old token as revoked
    db_token.revoked = True
    db_token.revoked_at = now

    return await _issue_refreshed_tokens(user, response, db)



class LogoutRequest(BaseModel):
    refresh_token: Optional[str] = None


@router.post("/logout")
async def logout(
    req: LogoutRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    refresh_token_val = (req and req.refresh_token) or request.cookies.get("refresh_token")
    if refresh_token_val:
        token_hash = hash_refresh_token(refresh_token_val)
        stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash).with_for_update()
        result = await db.execute(stmt)
        db_token = result.scalar_one_or_none()
        if db_token:
            db_token.revoked = True
            db_token.revoked_at = datetime.now(timezone.utc)
            db_token.revoked_by_logout = True
            await db.commit()
            
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    response.delete_cookie("csrftoken", path="/")
    return {"ok": True}


@router.get("/me", response_model=AuthUserResponse)
async def get_me(user: User = Depends(require_user)):

    return AuthUserResponse(
        id=user.id, 
        username=user.username, 
        email=user.email, 
        default_tags=user.default_tags
    )
