"""Bookmarks API — saved search queries."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db.database import get_db
from app.db.models import User, Bookmark
from app.api.deps import require_user
from app.services.booru import PROVIDERS

router = APIRouter(prefix="/api/bookmarks", tags=["bookmarks"])

# Bounds so a single account cannot fill the table: the write endpoints are
# otherwise unlimited and only protected by a per-IP rate limit.
MAX_BOOKMARKS_PER_USER = 500
MAX_QUERY_LENGTH = 2048


class BookmarkCreate(BaseModel):
    # name is String(255) and sites is a non-null ARRAY in app/db/models.py.
    name: str = Field(min_length=1, max_length=255)
    query: str = Field(max_length=MAX_QUERY_LENGTH)
    sites: List[str] = Field(max_length=len(PROVIDERS))

    @field_validator("sites")
    @classmethod
    def known_sites(cls, v: List[str]) -> List[str]:
        for site in v:
            if site not in PROVIDERS:
                raise ValueError(f"Unknown site: {site}")
        return v


class BookmarkResponse(BaseModel):
    id: int
    name: str
    query: str
    sites: List[str]


@router.get("")
async def list_bookmarks(
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """List bookmarks, most recent first, with a stable secondary sort."""
    result = await db.execute(
        select(Bookmark)
        .where(Bookmark.user_id == user.id)
        .order_by(Bookmark.created_at.desc(), Bookmark.id.desc())
    )
    bookmarks = result.scalars().all()
    return {
        "bookmarks": [
            {
                "id": b.id,
                "name": b.name,
                "query": b.query,
                "sites": b.sites or [],
            }
            for b in bookmarks
        ]
    }


@router.post("", status_code=201)
async def create_bookmark(
    body: BookmarkCreate,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    count = await db.scalar(
        select(func.count(Bookmark.id)).where(Bookmark.user_id == user.id)
    )
    if (count or 0) >= MAX_BOOKMARKS_PER_USER:
        raise HTTPException(
            status_code=409,
            detail=f"Bookmark limit reached ({MAX_BOOKMARKS_PER_USER})",
        )

    bookmark = Bookmark(
        user_id=user.id,
        name=body.name,
        query=body.query,
        sites=body.sites,
    )
    db.add(bookmark)
    await db.commit()
    await db.refresh(bookmark)
    return {"id": bookmark.id, "message": "Bookmark created"}


@router.delete("/{bookmark_id}")
async def delete_bookmark(
    bookmark_id: int,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Bookmark).where(
            Bookmark.id == bookmark_id, Bookmark.user_id == user.id
        )
    )
    bookmark = result.scalar_one_or_none()
    if not bookmark:
        raise HTTPException(status_code=404, detail="Bookmark not found")
    await db.delete(bookmark)
    await db.commit()
    return {"message": "Bookmark deleted"}
