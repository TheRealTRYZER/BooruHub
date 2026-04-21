"""Tag Mappings API — manage user's manual tag translations."""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.database import get_db
from app.db.models import User, UserTagMapping
from app.api.deps import require_user
from app.services.tag_mapping import invalidate_user_cache

router = APIRouter(prefix="/api/mappings", tags=["mappings"])


class MappingCreate(BaseModel):
    unitag: str = Field(min_length=1)
    danbooru_tags: str = ""
    e621_tags: str = ""
    rule34_tags: str = ""


class MappingUpdate(BaseModel):
    unitag: Optional[str] = None
    danbooru_tags: Optional[str] = None
    e621_tags: Optional[str] = None
    rule34_tags: Optional[str] = None


class MappingResponse(BaseModel):
    id: int
    unitag: str
    danbooru_tags: str
    e621_tags: str
    rule34_tags: str


class DefaultTagsUpdate(BaseModel):
    default_tags: str


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
    existing = await db.execute(
        select(UserTagMapping).where(
            UserTagMapping.user_id == user.id,
            UserTagMapping.unitag == body.unitag.strip().lower()
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, 
            detail="Mapping for this unitag already exists"
        )

    mapping = UserTagMapping(
        user_id=user.id,
        unitag=body.unitag.strip().lower(),
        danbooru_tags=body.danbooru_tags.strip(),
        e621_tags=body.e621_tags.strip(),
        rule34_tags=body.rule34_tags.strip(),
    )
    db.add(mapping)
    await db.commit()
    await db.refresh(mapping)
    
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
        mapping.unitag = body.unitag.strip().lower()
    if body.danbooru_tags is not None:
        mapping.danbooru_tags = body.danbooru_tags.strip()
    if body.e621_tags is not None:
        mapping.e621_tags = body.e621_tags.strip()
    if body.rule34_tags is not None:
        mapping.rule34_tags = body.rule34_tags.strip()

    await db.commit()
    await db.refresh(mapping)
    
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
