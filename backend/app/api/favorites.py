"""Favorites API — CRUD for user's favorite posts."""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db.database import get_db
from app.db.models import User, Favorite
from app.api.deps import require_user

router = APIRouter(prefix="/api/favorites", tags=["favorites"])


class FavoriteAdd(BaseModel):
    source_site: str
    post_id: str
    preview_url: Optional[str] = None
    file_url: Optional[str] = None
    sample_url: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    rating: Optional[str] = "g"
    score: int = 0
    is_dislike: bool = False


class FavoriteResponse(BaseModel):
    id: int
    source_site: str
    post_id: str
    preview_url: Optional[str]
    file_url: Optional[str]
    sample_url: Optional[str]
    tags: List[str]
    rating: Optional[str]
    score: int
    is_dislike: bool


@router.get("")
async def list_favorites(
    page: int = 1,
    limit: int = 40,
    is_dislike: bool = False,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    offset = (page - 1) * limit
    
    # 1. Get total count
    count_q = await db.execute(select(func.count()).where(
        Favorite.user_id == user.id,
        Favorite.is_dislike == is_dislike
    ))
    total_count = count_q.scalar() or 0

    # 2. Get subset
    result = await db.execute(
        select(Favorite)
        .where(
            Favorite.user_id == user.id,
            Favorite.is_dislike == is_dislike
        )
        .order_by(Favorite.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    favs = result.scalars().all()
    
    return {
        "favorites": [
            {
                "id": f.id,
                "source_site": f.source_site,
                "post_id": f.post_id,
                "preview_url": f.preview_url,
                "file_url": f.file_url,
                "sample_url": f.sample_url,
                "tags": f.tags or [],
                "rating": f.rating,
                "score": f.score,
            }
            for f in favs
        ],
        "page": page,
        "total": total_count
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def add_favorite(
    body: FavoriteAdd,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    # Check for duplicate
    existing = await db.execute(
        select(Favorite).where(
            Favorite.user_id == user.id,
            Favorite.source_site == body.source_site,
            Favorite.post_id == body.post_id,
        )
    )
    fav = existing.scalar_one_or_none()
    if fav:
        if fav.is_dislike == body.is_dislike:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, 
                detail="Item already in this list"
            )
        else:
            fav.is_dislike = body.is_dislike
            await db.commit()
            return {"id": fav.id, "message": "Updated item type"}

    fav = Favorite(
        user_id=user.id,
        source_site=body.source_site,
        post_id=body.post_id,
        preview_url=body.preview_url,
        file_url=body.file_url,
        sample_url=body.sample_url,
        tags=body.tags,
        rating=body.rating,
        score=body.score,
        is_dislike=body.is_dislike,
    )
    db.add(fav)
    await db.commit()
    await db.refresh(fav)
    return {"id": fav.id, "message": "Added item"}


@router.delete("/{fav_id}")
async def remove_favorite(
    fav_id: int,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Favorite).where(Favorite.id == fav_id, Favorite.user_id == user.id)
    )
    fav = result.scalar_one_or_none()
    if not fav:
        raise HTTPException(status_code=404, detail="Favorite not found")
    
    await db.delete(fav)
    await db.commit()
    return {"message": "Removed from favorites"}


@router.get("/check")
async def check_favorite(
    source_site: str,
    post_id: str,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """Instant check for PostGrid items."""
    result = await db.execute(
        select(Favorite).where(
            Favorite.user_id == user.id,
            Favorite.source_site == source_site,
            Favorite.post_id == post_id,
        )
    )
    f = result.scalar_one_or_none()
    return {
        "is_favorite": f is not None and not f.is_dislike,
        "is_dislike": f is not None and f.is_dislike,
        "favorite_id": f.id if f else None
    }
