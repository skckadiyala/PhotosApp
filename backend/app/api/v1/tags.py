import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.photo import Photo
from app.models.tag import PhotoTag, Tag
from app.models.user import User

router = APIRouter()


@router.get("")
async def list_tags(
    category: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(Tag).order_by(Tag.name)
    if category:
        query = query.where(Tag.category == category)
    result = await db.execute(query)
    return {"items": result.scalars().all()}


@router.get("/{tag_id}/photos")
async def get_photos_by_tag(
    tag_id: uuid.UUID,
    cursor: str | None = None,
    limit: int = Query(default=50, le=200),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    photos_q = (
        select(Photo)
        .join(PhotoTag, PhotoTag.photo_id == Photo.id)
        .where(PhotoTag.tag_id == tag_id, Photo.user_id == user.id)
        .order_by(Photo.taken_at.desc().nullslast())
        .limit(limit)
    )
    result = await db.execute(photos_q)
    return {"items": result.scalars().all()}
