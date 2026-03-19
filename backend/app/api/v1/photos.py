"""
Phase 1: Photo API endpoints.

GET /api/v1/photos?page=1&limit=50&sort=date_taken
GET /api/v1/photos/{photo_id}
GET /api/v1/photos/{photo_id}/thumbnail?size=medium
GET /api/v1/photos/{photo_id}/original
GET /api/v1/photos/metadata/{photo_id}
"""
import logging
import os
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, get_current_user_token_param
from app.config import get_settings
from app.core.database import get_db
from app.models.photo import Photo
from app.models.user import User
from app.schemas.photo import PhotoBase, PhotoDetail, PhotoMetadataResponse, PaginatedPhotos
from app.utils.path import safe_resolve

router = APIRouter()
settings = get_settings()
logger = logging.getLogger(__name__)

VALID_THUMB_SIZES = {"small": "sm", "medium": "md", "large": "lg", "sm": "sm", "md": "md", "lg": "lg"}
VALID_SORT_FIELDS = {"date_taken", "created_at", "file_name", "file_size"}


@router.get("", response_model=PaginatedPhotos)
async def list_photos(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    sort: str = Query(default="date_taken"),
    media_type: str = Query(default=None, description="'video' to list only videos, 'image' for images only"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List photos with page/limit pagination, sorted by the given field descending."""
    base_filter = [Photo.user_id == user.id, Photo.is_hidden.is_(False)]

    # Filter by media type via mime_type prefix
    if media_type == "video":
        base_filter.append(Photo.mime_type.like("video/%"))
    elif media_type == "image":
        base_filter.append(Photo.mime_type.like("image/%"))

    query = select(Photo).where(*base_filter)

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
    count_q = select(func.count()).select_from(Photo).where(*base_filter)
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
    if settings.host_photos_dir:
        import os as _os
        detail.host_file_path = _os.path.join(settings.host_photos_dir, photo.file_path)
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


@router.get("/{photo_id}/stream")
async def stream_video(
    photo_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_token_param),
):
    """Stream a video file using a ?token= query param (for <video> tags that
    cannot send Authorization headers)."""
    photo = await _get_photo_or_404(db, photo_id, user.id)

    if not photo.mime_type.startswith("video/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Not a video file")

    full_path = safe_resolve(settings.photos_dir, photo.file_path)
    if not os.path.isfile(full_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video file not found on disk")

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
            "Accept-Ranges": "bytes",
        },
    )


@router.post("/{photo_id}/scan-faces")
async def scan_faces_for_photo(
    photo_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Re-run face detection on a single photo and recluster faces for the user."""
    photo = await _get_photo_or_404(db, photo_id, user.id)

    abs_path = os.path.join(settings.photos_dir, photo.file_path)
    if not os.path.isfile(abs_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Photo file not found on disk",
        )

    user_id_str = str(user.id)
    photo_id_str = str(photo_id)

    def _run():
        from app.core.database import get_sync_db
        from app.services.face_detector import detect_faces_in_photo
        from app.services.face_cluster import cluster_faces
        from app.models.face import Face as FaceModel
        from sqlalchemy import delete as sql_delete, select as sql_select

        def _iou(a, b):
            """Intersection-over-Union for two (top,right,bottom,left) boxes."""
            inter_top    = max(a["top"],    b["top"])
            inter_left   = max(a["left"],   b["left"])
            inter_bottom = min(a["bottom"], b["bottom"])
            inter_right  = min(a["right"],  b["right"])
            inter_w = max(0, inter_right  - inter_left)
            inter_h = max(0, inter_bottom - inter_top)
            inter   = inter_w * inter_h
            if inter == 0:
                return 0.0
            area_a = (a["right"] - a["left"]) * (a["bottom"] - a["top"])
            area_b = (b["right"] - b["left"]) * (b["bottom"] - b["top"])
            return inter / (area_a + area_b - inter)

        db_sync = get_sync_db()
        try:
            # Step 1: detect faces — abort early if detection itself raises
            new_faces = detect_faces_in_photo(abs_path)
            logger.info("scan-faces: detected %d face(s) in %s", len(new_faces), abs_path)

            # Step 2: load existing face records so we can preserve person assignments
            existing = db_sync.execute(
                sql_select(FaceModel).where(FaceModel.photo_id == photo_id_str)
            ).scalars().all()

            # Step 3: match each new detection to the closest existing face (by IoU)
            # Carry forward the person_id when IoU > 0.4 (same face, same spot)
            IOU_THRESHOLD = 0.4
            used_existing_ids: set = set()
            new_records = []
            for face_data in new_faces:
                loc = face_data["location"]
                best_iou, best_existing = 0.0, None
                for ex in existing:
                    ex_loc = {"top": ex.bbox_top, "right": ex.bbox_right,
                              "bottom": ex.bbox_bottom, "left": ex.bbox_left}
                    iou = _iou(loc, ex_loc)
                    if iou > best_iou:
                        best_iou, best_existing = iou, ex
                inherited_person_id = None
                if best_existing and best_iou >= IOU_THRESHOLD:
                    inherited_person_id = best_existing.person_id
                    used_existing_ids.add(best_existing.id)
                new_records.append((loc, face_data["embedding"], inherited_person_id))

            # Step 4: delete ALL existing face records for this photo
            db_sync.execute(sql_delete(FaceModel).where(FaceModel.photo_id == photo_id_str))
            db_sync.commit()

            # Step 5: store newly detected faces (with inherited person_id where matched)
            for loc, embedding, person_id in new_records:
                db_sync.add(FaceModel(
                    photo_id=photo_id_str,
                    bbox_top=loc["top"],
                    bbox_right=loc["right"],
                    bbox_bottom=loc["bottom"],
                    bbox_left=loc["left"],
                    embedding=embedding.tolist(),
                    confidence=1.0,
                    person_id=str(person_id) if person_id else None,
                ))
            db_sync.commit()

            # Step 6: recluster all faces for this user
            cluster_faces(user_id_str)

        except Exception:
            db_sync.rollback()
            logger.error("scan-faces failed for photo %s", photo_id_str, exc_info=True)
        finally:
            db_sync.close()

    background_tasks.add_task(_run)
    return {"message": "Face scan started for this photo", "photo_id": photo_id_str, "status": "running"}


class ManualFaceRegion(BaseModel):
    """Bounding box in original image pixel coordinates (face_recognition order)."""
    top: int
    right: int
    bottom: int
    left: int


@router.post("/{photo_id}/faces/manual")
async def add_manual_face(
    photo_id: uuid.UUID,
    region: ManualFaceRegion,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Store an embedding for a user-drawn face bounding box on a single photo."""
    photo = await _get_photo_or_404(db, photo_id, user.id)

    abs_path = os.path.join(settings.photos_dir, photo.file_path)
    if not os.path.isfile(abs_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Photo file not found on disk",
        )

    # Basic sanity checks on the bounding box
    if region.top >= region.bottom or region.left >= region.right:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="Invalid bounding box: top must be < bottom and left must be < right")
    if (region.bottom - region.top) < 20 or (region.right - region.left) < 20:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="Selected region is too small (minimum 20x20 pixels)")

    user_id_str = str(user.id)
    photo_id_str = str(photo_id)
    loc = (region.top, region.right, region.bottom, region.left)

    def _run():
        import face_recognition
        import numpy as np
        from PIL import Image, ImageOps
        from app.core.database import get_sync_db
        from app.models.face import Face as FaceModel
        from app.services.face_cluster import cluster_faces

        db_sync = get_sync_db()
        try:
            pil = ImageOps.exif_transpose(Image.open(abs_path)).convert("RGB")
            img = np.array(pil)

            # Compute 128-d embedding for the explicitly provided bounding box
            encodings = face_recognition.face_encodings(img, known_face_locations=[loc], num_jitters=3)
            if not encodings:
                logger.warning("manual-face: could not compute embedding for %s region %s", abs_path, loc)
                return

            top, right, bottom, left = loc
            db_sync.add(FaceModel(
                photo_id=photo_id_str,
                bbox_top=top,
                bbox_right=right,
                bbox_bottom=bottom,
                bbox_left=left,
                embedding=encodings[0].tolist(),
                confidence=0.9,  # user-confirmed, high confidence
            ))
            db_sync.commit()
            logger.info("manual-face: stored face for photo %s at %s", photo_id_str, loc)

            cluster_faces(user_id_str)
        except Exception:
            db_sync.rollback()
            logger.error("manual-face: failed for photo %s", photo_id_str, exc_info=True)
        finally:
            db_sync.close()

    background_tasks.add_task(_run)
    return {"message": "Manual face region queued for processing", "photo_id": photo_id_str, "status": "running"}

async def _get_photo_or_404(db: AsyncSession, photo_id: uuid.UUID, user_id: uuid.UUID) -> Photo:
    result = await db.execute(
        select(Photo).where(Photo.id == photo_id, Photo.user_id == user_id)
    )
    photo = result.scalar_one_or_none()
    if not photo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found")
    return photo
