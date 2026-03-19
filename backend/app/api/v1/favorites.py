import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.photo import Photo
from app.models.user import User

router = APIRouter()


@router.get("")
async def list_favorites(
    cursor: str | None = None,
    limit: int = Query(default=50, le=200),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = (
        select(Photo)
        .where(Photo.user_id == user.id, Photo.is_favorite.is_(True))
        .order_by(Photo.taken_at.desc().nullslast())
        .limit(limit)
    )
    result = await db.execute(query)
    return {"items": result.scalars().all()}


@router.post("/{photo_id}")
async def add_favorite(
    photo_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Photo).where(Photo.id == photo_id, Photo.user_id == user.id))
    photo = result.scalar_one_or_none()
    if not photo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found")
    photo.is_favorite = True
    await db.commit()
    await db.refresh(photo)
    return photo


@router.delete("/{photo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_favorite(
    photo_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Photo).where(Photo.id == photo_id, Photo.user_id == user.id))
    photo = result.scalar_one_or_none()
    if not photo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found")
    photo.is_favorite = False
    await db.commit()
