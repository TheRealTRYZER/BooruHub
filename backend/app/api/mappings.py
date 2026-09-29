"""Tag Mappings API — manage user's manual tag translations."""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError

from app.db.database import get_db
from app.db.models import User, UserTagMapping
from app.api.deps import require_user
from app.services.tag_mapping import invalidate_user_cache

router = APIRouter(prefix="/api/mappings", tags=["mappings"])

# All mapping columns are String(255); wider values raised a DataError.
MAX_UNITAG_LENGTH = 255
MAX_MAPPINGS_PER_USER = 500


class MappingCreate(BaseModel):
    unitag: str = Field(min_length=1, max_length=MAX_UNITAG_LENGTH)
    danbooru_tags: str = Field(default="", max_length=MAX_UNITAG_LENGTH)
    e621_tags: str = Field(default="", max_length=MAX_UNITAG_LENGTH)
    rule34_tags: str = Field(default="", max_length=MAX_UNITAG_LENGTH)


class MappingUpdate(BaseModel):
    unitag: Optional[str] = Field(default=None, min_length=1, max_length=MAX_UNITAG_LENGTH)
    danbooru_tags: Optional[str] = Field(default=None, max_length=MAX_UNITAG_LENGTH)
    e621_tags: Optional[str] = Field(default=None, max_length=MAX_UNITAG_LENGTH)
    rule34_tags: Optional[str] = Field(default=None, max_length=MAX_UNITAG_LENGTH)


class MappingResponse(BaseModel):
    id: int
    unitag: str
    danbooru_tags: str
    e621_tags: str
    rule34_tags: str


class DefaultTagsUpdate(BaseModel):
    # users.default_tags is String(255).
    default_tags: str = Field(default="", max_length=255)


@router.get("", response_model=List[MappingResponse])
async def list_mappings(
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserTagMapping).where(UserTagMapping.user_id == user.id)
    )
    return result.scalars().all()


@router.post("", response_model=MappingResponse, status_code=status.HTTP_201_CREATED)
async def create_mapping(
    body: MappingCreate,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    # Check if unitag already exists for this user
    unitag = body.unitag.strip().lower()
    if not unitag:
        raise HTTPException(status_code=422, detail="unitag cannot be empty")

    existing = await db.execute(
        select(UserTagMapping).where(
            UserTagMapping.user_id == user.id,
            UserTagMapping.unitag == unitag
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Mapping for this unitag already exists"
        )

    count = await db.scalar(
        select(func.count(UserTagMapping.id)).where(UserTagMapping.user_id == user.id)
    )
    if (count or 0) >= MAX_MAPPINGS_PER_USER:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Mapping limit reached ({MAX_MAPPINGS_PER_USER})",
        )

    mapping = UserTagMapping(
        user_id=user.id,
        unitag=unitag,
        danbooru_tags=body.danbooru_tags.strip(),
        e621_tags=body.e621_tags.strip(),
        rule34_tags=body.rule34_tags.strip(),
    )
    db.add(mapping)
    try:
        await db.commit()
        await db.refresh(mapping)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Mapping for this unitag already exists"
        )
    
    # Cache MUST be cleared for updates to be instant
    await invalidate_user_cache(user.id)
    return mapping


@router.put("/{mapping_id}", response_model=MappingResponse)
async def update_mapping(
    mapping_id: int,
    body: MappingUpdate,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserTagMapping).where(
            UserTagMapping.id == mapping_id,
            UserTagMapping.user_id == user.id
        )
    )
    mapping = result.scalar_one_or_none()
    if not mapping:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mapping not found")

    if body.unitag is not None:
        new_unitag = body.unitag.strip().lower()
        if not new_unitag:
            raise HTTPException(status_code=422, detail="unitag cannot be empty")
        # Pre-check unitag uniqueness excluding the current id (B-M16)
        existing = await db.execute(
            select(UserTagMapping).where(
                UserTagMapping.user_id == user.id,
                UserTagMapping.unitag == new_unitag,
                UserTagMapping.id != mapping_id
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Mapping for this unitag already exists"
            )
        mapping.unitag = new_unitag

    if body.danbooru_tags is not None:
        mapping.danbooru_tags = body.danbooru_tags.strip()
    if body.e621_tags is not None:
        mapping.e621_tags = body.e621_tags.strip()
    if body.rule34_tags is not None:
        mapping.rule34_tags = body.rule34_tags.strip()

    try:
        await db.commit()
        await db.refresh(mapping)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Mapping for this unitag already exists"
        )
    
    # Clear cache
    await invalidate_user_cache(user.id)
    return mapping


@router.delete("/{mapping_id}")
async def delete_mapping(
    mapping_id: int,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserTagMapping).where(
            UserTagMapping.id == mapping_id,
            UserTagMapping.user_id == user.id
        )
    )
    mapping = result.scalar_one_or_none()
    if not mapping:
        raise HTTPException(status_code=404, detail="Mapping not found")

    await db.delete(mapping)
    await db.commit()
    
    # Clear cache
    await invalidate_user_cache(user.id)
    return {"message": "Mapping deleted"}


@router.put("/user/default-tags")
async def update_default_tags(
    body: DefaultTagsUpdate,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    user.default_tags = body.default_tags.strip().lower()
    await db.commit()
    return {"message": "Default tags updated", "default_tags": user.default_tags}
