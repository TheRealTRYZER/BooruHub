from datetime import datetime, timezone, timedelta
import re
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.exc import IntegrityError

from app.db.database import get_db
from app.core.config import get_settings
from app.db.models import User, UserTagMapping, RefreshToken
from app.core.security import (
    hash_password, verify_password, create_access_token, create_refresh_token,
    decode_refresh_token, hash_refresh_token
)
from app.api.deps import require_user
from app.core.defaults import DEFAULT_USER_TAGS, STARTER_MAPPINGS
from app.core.rate_limit import rate_limit

router = APIRouter(prefix="/api/auth", tags=["auth"])


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
        if not re.match(r"^[a-zA-Z0-9_-]+$", v):
            raise ValueError("Username may only contain letters, digits, underscores and hyphens")
        return v



class LoginRequest(BaseModel):
    login: str = Field(description="Username or email")
    password: str


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
        # Existing checks
        existing_q = await db.execute(
            select(User).where((User.username == req.username) | (User.email == req.email))
        )
        if existing_q.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, 
                detail="Username or email already taken"
            )

        # 1. Create User
        user = User(
            username=req.username,
            email=req.email,
            password_hash=hash_password(req.password),
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
    result = await db.execute(
        select(User).where((User.username == req.login) | (User.email == req.login))
    )
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Invalid credentials"
        )

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

    if db_token.revoked:
        # Replay attack: revoke all tokens for this user
        await db.execute(
            update(RefreshToken).where(RefreshToken.user_id == db_token.user_id).values(revoked=True)
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked refresh token",
        )

    if db_token.expires_at < datetime.now(timezone.utc):
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

    # Generate new tokens
    new_access = create_access_token({"sub": str(user.id)})
    new_refresh = create_refresh_token({"sub": str(user.id)})

    # Save new refresh token in DB
    new_db_refresh = RefreshToken(
        user_id=user.id,
        token_hash=hash_refresh_token(new_refresh),
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
    )
    db.add(new_db_refresh)
    
    # B-M1: Clean up expired and old revoked tokens
    await db.execute(
        delete(RefreshToken).where(
            (RefreshToken.expires_at < datetime.now(timezone.utc)) |
            ((RefreshToken.revoked == True) & (RefreshToken.created_at < datetime.now(timezone.utc) - timedelta(days=30)))
        )
    )
    
    await db.commit()

    settings = get_settings()
    response.set_cookie("access_token", new_access, httponly=True, secure=settings.COOKIE_SECURE, samesite=settings.COOKIE_SAMESITE, path="/")
    response.set_cookie("refresh_token", new_refresh, httponly=True, secure=settings.COOKIE_SECURE, samesite=settings.COOKIE_SAMESITE, path="/")

    return {
        "access_token": new_access,
        "refresh_token": new_refresh,
        "token_type": "bearer",
    }



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
