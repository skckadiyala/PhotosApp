import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.album import Album, AlbumPhoto
from app.models.photo import Photo
from app.models.user import User
from app.schemas.album import AlbumCreate, AlbumResponse, AlbumUpdate, AlbumPhotoAdd

router = APIRouter()


@router.get("")
async def list_albums(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Album).where(Album.user_id == user.id).order_by(Album.updated_at.desc())
    )
    albums = result.scalars().all()

    # Backfill cover_photo_id for albums that have photos but no cover set
    for album in albums:
        if not album.cover_photo_id and album.photo_count > 0:
            first = await db.execute(
                select(AlbumPhoto.photo_id)
                .where(AlbumPhoto.album_id == album.id)
                .order_by(AlbumPhoto.sort_order)
                .limit(1)
            )
            photo_id = first.scalar_one_or_none()
            if photo_id:
                album.cover_photo_id = photo_id

    return {"items": albums}


@router.post("", response_model=AlbumResponse, status_code=status.HTTP_201_CREATED)
async def create_album(
    body: AlbumCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    album = Album(name=body.name, description=body.description, user_id=user.id)
    db.add(album)
    await db.flush()
    return album


@router.get("/{album_id}")
async def get_album(
    album_id: uuid.UUID,
    cursor: str | None = None,
    limit: int = Query(default=50, le=200),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Album).where(Album.id == album_id, Album.user_id == user.id))
    album = result.scalar_one_or_none()
    if not album:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Album not found")

    photos_q = (
        select(Photo)
        .join(AlbumPhoto, AlbumPhoto.photo_id == Photo.id)
        .where(AlbumPhoto.album_id == album_id)
        .order_by(AlbumPhoto.sort_order)
        .limit(limit + 1)
    )
    photos_result = await db.execute(photos_q)
    items = list(photos_result.scalars().all())

    next_cursor = None
    if len(items) > limit:
        items = items[:limit]
        next_cursor = str(items[-1].id)

    return {"album": album, "items": items, "next_cursor": next_cursor}


@router.put("/{album_id}", response_model=AlbumResponse)
async def update_album(
    album_id: uuid.UUID,
    body: AlbumUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Album).where(Album.id == album_id, Album.user_id == user.id))
    album = result.scalar_one_or_none()
    if not album:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Album not found")

    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(album, key, value)
    await db.flush()
    return album


@router.delete("/{album_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_album(
    album_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Album).where(Album.id == album_id, Album.user_id == user.id))
    album = result.scalar_one_or_none()
    if not album:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Album not found")
    await db.delete(album)


@router.post("/{album_id}/photos")
async def add_photos_to_album(
    album_id: uuid.UUID,
    body: AlbumPhotoAdd,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Album).where(Album.id == album_id, Album.user_id == user.id))
    album = result.scalar_one_or_none()
    if not album:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Album not found")

    added = 0
    for photo_id in body.photo_ids:
        existing = await db.execute(
            select(AlbumPhoto).where(AlbumPhoto.album_id == album_id, AlbumPhoto.photo_id == photo_id)
        )
        if not existing.scalar_one_or_none():
            db.add(AlbumPhoto(album_id=album_id, photo_id=photo_id, sort_order=added))
            added += 1

    album.photo_count = (album.photo_count or 0) + added

    # Auto-set cover photo if not already set
    if not album.cover_photo_id and added > 0:
        album.cover_photo_id = body.photo_ids[0]

    await db.flush()
    return {"added": added}


@router.delete("/{album_id}/photos", status_code=status.HTTP_204_NO_CONTENT)
async def remove_photos_from_album(
    album_id: uuid.UUID,
    body: AlbumPhotoAdd,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    for photo_id in body.photo_ids:
        result = await db.execute(
            select(AlbumPhoto).where(AlbumPhoto.album_id == album_id, AlbumPhoto.photo_id == photo_id)
        )
        ap = result.scalar_one_or_none()
        if ap:
            await db.delete(ap)

    # Update count
    count_result = await db.execute(
        select(func.count()).select_from(AlbumPhoto).where(AlbumPhoto.album_id == album_id)
    )
    result = await db.execute(select(Album).where(Album.id == album_id))
    album = result.scalar_one_or_none()
    if album:
        album.photo_count = count_result.scalar()
