"""Auth API — register, login, current user."""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.database import get_db
from app.db.models import User, UserTagMapping
from app.core.security import hash_password, verify_password, create_access_token
from app.api.deps import require_user
from app.core.defaults import DEFAULT_USER_TAGS, STARTER_MAPPINGS

router = APIRouter(prefix="/api/auth", tags=["auth"])


class AuthUserResponse(BaseModel):
    id: int
    username: str
    email: str
    default_tags: str


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    data_consent: bool = False


class LoginRequest(BaseModel):
    login: str = Field(description="Username or email")
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: AuthUserResponse


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
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
    
    await db.commit()
    await db.refresh(user)

    token = create_access_token({"sub": str(user.id)})
    return TokenResponse(
        access_token=token,
        user=AuthUserResponse(
            id=user.id, 
            username=user.username, 
            email=user.email, 
            default_tags=user.default_tags
        ),
    )


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
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
    return TokenResponse(
        access_token=token,
        user=AuthUserResponse(
            id=user.id, 
            username=user.username, 
            email=user.email, 
            default_tags=user.default_tags
        ),
    )


@router.get("/me", response_model=AuthUserResponse)
async def get_me(user: User = Depends(require_user)):
    return AuthUserResponse(
        id=user.id, 
        username=user.username, 
        email=user.email, 
        default_tags=user.default_tags
    )
