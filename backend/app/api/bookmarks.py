"""Bookmarks API — saved search queries."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.database import get_db
from app.db.models import User, Bookmark
from app.api.deps import require_user

router = APIRouter(prefix="/api/bookmarks", tags=["bookmarks"])


class BookmarkCreate(BaseModel):
    name: str
    query: str
    sites: List[str]


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
    result = await db.execute(
        select(Bookmark)
        .where(Bookmark.user_id == user.id)
        .order_by(Bookmark.created_at.desc())
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
