"""
Phase 1: Photo API endpoints.

GET /api/v1/photos?page=1&limit=50&sort=date_taken
GET /api/v1/photos/{photo_id}
GET /api/v1/photos/{photo_id}/thumbnail?size=medium
GET /api/v1/photos/{photo_id}/original
GET /api/v1/photos/metadata/{photo_id}
"""
import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.config import get_settings
from app.core.database import get_db
from app.models.photo import Photo
from app.models.user import User
from app.schemas.photo import PhotoBase, PhotoDetail, PhotoMetadataResponse, PaginatedPhotos
from app.utils.path import safe_resolve

router = APIRouter()
settings = get_settings()

VALID_THUMB_SIZES = {"small": "sm", "medium": "md", "large": "lg", "sm": "sm", "md": "md", "lg": "lg"}
VALID_SORT_FIELDS = {"date_taken", "created_at", "file_name", "file_size"}


@router.get("", response_model=PaginatedPhotos)
async def list_photos(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    sort: str = Query(default="date_taken"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List photos with page/limit pagination, sorted by the given field descending."""
    query = select(Photo).where(Photo.user_id == user.id, Photo.is_hidden.is_(False))

    # Sort
    if sort == "date_taken":
        query = query.order_by(Photo.taken_at.desc().nullslast(), Photo.created_at.desc())
    elif sort == "created_at":
        query = query.order_by(Photo.created_at.desc())
    elif sort == "file_name":
        query = query.order_by(Photo.file_name.asc())
    elif sort == "file_size":
        query = query.order_by(Photo.file_size.desc())
    else:
        query = query.order_by(Photo.taken_at.desc().nullslast(), Photo.created_at.desc())

    # Count total
    count_q = select(func.count()).select_from(Photo).where(
        Photo.user_id == user.id, Photo.is_hidden.is_(False)
    )
    total = (await db.execute(count_q)).scalar() or 0

    # Paginate
    offset = (page - 1) * limit
    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    items = list(result.scalars().all())

    total_pages = (total + limit - 1) // limit if total > 0 else 1

    return PaginatedPhotos(
        items=items,
        page=page,
        limit=limit,
        total=total,
        total_pages=total_pages,
    )


@router.get("/metadata/{photo_id}", response_model=PhotoMetadataResponse)
async def get_photo_metadata(
    photo_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get detailed EXIF metadata for a photo."""
    photo = await _get_photo_or_404(db, photo_id, user.id)
    return photo


@router.get("/{photo_id}", response_model=PhotoDetail)
async def get_photo(
    photo_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get a single photo by ID."""
    result = await db.execute(
        select(Photo)
        .options(selectinload(Photo.location))
        .where(Photo.id == photo_id, Photo.user_id == user.id)
    )
    photo = result.scalar_one_or_none()
    if not photo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found")

    location_name = None
    if photo.location:
        parts = [p for p in [photo.location.city, photo.location.state, photo.location.country] if p]
        location_name = ", ".join(parts) if parts else photo.location.formatted

    detail = PhotoDetail.model_validate(photo)
    detail.location_name = location_name
    return detail


@router.get("/{photo_id}/thumbnail")
async def serve_thumbnail(
    photo_id: uuid.UUID,
    size: str = Query(default="medium"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Serve a thumbnail image.
    size: small (200px), medium (800px), or large (1600px).
    """
    size_key = VALID_THUMB_SIZES.get(size)
    if not size_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid size '{size}'. Use: small, medium, large",
        )

    photo = await _get_photo_or_404(db, photo_id, user.id)

    thumb_rel = getattr(photo, f"thumb_{size_key}")
    if not thumb_rel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Thumbnail not generated yet",
        )

    thumb_path = safe_resolve(settings.thumbnails_dir, thumb_rel)
    if not os.path.isfile(thumb_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Thumbnail file missing from disk",
        )

    return FileResponse(
        thumb_path,
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


@router.get("/{photo_id}/original")
async def serve_original(
    photo_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Stream the full original photo file."""
    photo = await _get_photo_or_404(db, photo_id, user.id)

    full_path = safe_resolve(settings.photos_dir, photo.file_path)
    if not os.path.isfile(full_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Original file not found on disk",
        )

    file_size = os.path.getsize(full_path)

    def _stream():
        with open(full_path, "rb") as f:
            while chunk := f.read(1024 * 64):
                yield chunk

    return StreamingResponse(
        _stream(),
        media_type=photo.mime_type,
        headers={
            "Content-Disposition": f'inline; filename="{photo.file_name}"',
            "Content-Length": str(file_size),
            "Cache-Control": "public, max-age=86400",
        },
    )


# ── Helper ───────────────────────────────────────────────────

async def _get_photo_or_404(db: AsyncSession, photo_id: uuid.UUID, user_id: uuid.UUID) -> Photo:
    result = await db.execute(
        select(Photo).where(Photo.id == photo_id, Photo.user_id == user_id)
    )
    photo = result.scalar_one_or_none()
    if not photo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found")
    return photo
