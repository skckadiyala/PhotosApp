"""
Phase 2: Face API endpoints.

GET  /api/v1/faces           — list all detected face clusters (grouped by person)
GET  /api/v1/faces/{face_id}/thumbnail — serve a cropped face thumbnail
POST /api/v1/faces/detect    — trigger face detection on unprocessed photos
POST /api/v1/faces/cluster   — run DBSCAN clustering on all embeddings
POST /api/v1/faces/merge     — merge two face clusters manually
"""
import os
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_admin
from app.config import get_settings
from app.core.database import get_db
from app.models.face import Face
from app.models.person import Person
from app.models.photo import Photo
from app.models.user import User
from app.schemas.face import (
    FaceBase,
    FaceAssignRequest,
    MergePeopleRequest,
)
from app.utils.path import safe_resolve

router = APIRouter()
settings = get_settings()


@router.get("", response_model=list[FaceBase])
async def list_faces(
    person_id: uuid.UUID | None = None,
    unassigned: bool = False,
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    List detected faces. Filter by person_id or unassigned.
    """
    query = (
        select(Face)
        .join(Photo, Face.photo_id == Photo.id)
        .where(Photo.user_id == user.id)
    )

    if unassigned:
        query = query.where(Face.person_id.is_(None))
    elif person_id:
        query = query.where(Face.person_id == person_id)

    query = query.order_by(Face.created_at.desc()).limit(limit)
    result = await db.execute(query)
    return list(result.scalars().all())


@router.get("/{face_id}/thumbnail")
async def serve_face_thumbnail(
    face_id: uuid.UUID,
    size: int = Query(default=200, ge=50, le=800),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Serve a cropped face thumbnail, generated on-demand and cached on disk."""
    result = await db.execute(
        select(Face)
        .join(Photo, Face.photo_id == Photo.id)
        .where(Face.id == face_id, Photo.user_id == user.id)
    )
    face = result.scalar_one_or_none()
    if not face:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Face not found")

    # Check for cached crop
    crops_dir = os.path.join(settings.thumbnails_dir, "face_crops")
    crop_filename = f"{face.id}_{size}.jpg"
    crop_path = os.path.join(crops_dir, crop_filename)

    if not os.path.isfile(crop_path):
        # Load the source photo and crop
        photo_result = await db.execute(select(Photo).where(Photo.id == face.photo_id))
        photo = photo_result.scalar_one_or_none()
        if not photo:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found")

        # Prefer medium thumbnail as source; fall back to original
        source_path = None
        if photo.thumb_md:
            candidate = safe_resolve(settings.thumbnails_dir, photo.thumb_md)
            if os.path.isfile(candidate):
                source_path = candidate
        if not source_path:
            source_path = safe_resolve(settings.photos_dir, photo.file_path)
        if not os.path.isfile(source_path):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source image not found")

        from PIL import Image

        img = Image.open(source_path)
        img_w, img_h = img.size

        # face_recognition bbox is (top, right, bottom, left) relative to original image.
        # If we're cropping from the thumbnail, scale the bbox proportionally.
        # We need the original image dimensions from the photo record.
        orig_w = photo.width or img_w
        orig_h = photo.height or img_h
        scale_x = img_w / orig_w
        scale_y = img_h / orig_h

        top = int(face.bbox_top * scale_y)
        right = int(face.bbox_right * scale_x)
        bottom = int(face.bbox_bottom * scale_y)
        left = int(face.bbox_left * scale_x)

        # Add padding (25%) for context around the face
        face_w = right - left
        face_h = bottom - top
        pad_x = int(face_w * 0.25)
        pad_y = int(face_h * 0.25)

        crop_left = max(0, left - pad_x)
        crop_top = max(0, top - pad_y)
        crop_right = min(img_w, right + pad_x)
        crop_bottom = min(img_h, bottom + pad_y)

        cropped = img.crop((crop_left, crop_top, crop_right, crop_bottom))
        cropped = cropped.resize((size, size), Image.LANCZOS)

        os.makedirs(crops_dir, exist_ok=True)
        cropped.save(crop_path, "JPEG", quality=90)

    return FileResponse(
        crop_path,
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


@router.post("/detect")
async def trigger_face_detection(
    background_tasks: BackgroundTasks,
    user: User = Depends(require_admin),
):
    """Trigger face detection on all photos missing face data (admin only). Runs in background."""
    from app.services.face_detector import process_all_photos

    background_tasks.add_task(process_all_photos, user_id=str(user.id))
    return {"message": "Face detection started", "status": "running"}


@router.delete("/{face_id}")
async def delete_face(
    face_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Delete a single face record. Cleans up the owning Person if no faces remain."""
    face = await db.get(Face, face_id)
    if not face:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Face not found")

    person_id = face.person_id
    await db.delete(face)
    await db.flush()

    # Clean up orphaned person
    if person_id:
        remaining = await db.scalar(select(func.count(Face.id)).where(Face.person_id == person_id))
        if remaining == 0:
            person = await db.get(Person, person_id)
            if person:
                await db.delete(person)

    await db.commit()
    return {"message": "Face deleted"}


@router.put("/{face_id}/assign")
async def assign_face(
    face_id: uuid.UUID,
    body: FaceAssignRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Assign a face to an existing person, or create a new person with a name."""
    result = await db.execute(
        select(Face)
        .join(Photo, Face.photo_id == Photo.id)
        .where(Face.id == face_id, Photo.user_id == user.id)
    )
    face = result.scalar_one_or_none()
    if not face:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Face not found")

    old_person_id = face.person_id

    if body.person_id:
        # Assign to existing person
        person_result = await db.execute(
            select(Person).where(Person.id == body.person_id, Person.user_id == user.id)
        )
        target_person = person_result.scalar_one_or_none()
        if not target_person:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target person not found")
        face.person_id = target_person.id
    elif body.new_person_name:
        # Create a new person with this name
        new_person = Person(user_id=user.id, name=body.new_person_name, face_count=0)
        db.add(new_person)
        await db.flush()
        face.person_id = new_person.id
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either person_id or new_person_name",
        )

    # Update face counts
    if old_person_id:
        old_count = (await db.execute(
            select(func.count()).select_from(Face).where(Face.person_id == old_person_id)
        )).scalar() or 0
        old_person = (await db.execute(select(Person).where(Person.id == old_person_id))).scalar_one_or_none()
        if old_person:
            old_person.face_count = old_count
            # Delete the old person if no faces remain
            if old_count == 0:
                await db.delete(old_person)

    new_person_id = face.person_id
    new_count = (await db.execute(
        select(func.count()).select_from(Face).where(Face.person_id == new_person_id)
    )).scalar() or 0
    new_person_obj = (await db.execute(select(Person).where(Person.id == new_person_id))).scalar_one_or_none()
    if new_person_obj:
        new_person_obj.face_count = new_count

    return {
        "face_id": str(face.id),
        "person_id": str(new_person_id),
        "person_name": new_person_obj.name if new_person_obj else None,
    }


# ---------- Face confirmation endpoints ----------

@router.get("/confirm", response_model=list[dict])
async def list_faces_to_confirm(
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return faces that need user confirmation (status='pending'), with suggested person info."""
    result = await db.execute(
        select(Face)
        .join(Photo, Face.photo_id == Photo.id)
        .where(Photo.user_id == user.id, Face.status == "pending", Face.person_id.isnot(None))
        .order_by(Face.match_distance.desc())
        .limit(limit)
    )
    faces = list(result.scalars().all())

    # Gather person info for each face
    person_ids = {f.person_id for f in faces if f.person_id}
    persons_result = await db.execute(
        select(Person).where(Person.id.in_(person_ids))
    )
    persons_map = {p.id: p for p in persons_result.scalars().all()}

    items = []
    for f in faces:
        person = persons_map.get(f.person_id)
        # Get a confirmed face from the same person to show as reference
        ref_face_result = await db.execute(
            select(Face)
            .where(
                Face.person_id == f.person_id,
                Face.id != f.id,
                Face.status == "confirmed",
            )
            .order_by(Face.match_distance.asc())
            .limit(1)
        )
        ref_face = ref_face_result.scalar_one_or_none()

        items.append({
            "id": str(f.id),
            "photo_id": str(f.photo_id),
            "person_id": str(f.person_id) if f.person_id else None,
            "person_name": person.name if person else None,
            "match_distance": f.match_distance,
            "status": f.status,
            "confidence": f.confidence,
            "bbox_top": f.bbox_top,
            "bbox_right": f.bbox_right,
            "bbox_bottom": f.bbox_bottom,
            "bbox_left": f.bbox_left,
            "reference_face_id": str(ref_face.id) if ref_face else None,
            "created_at": f.created_at.isoformat() if f.created_at else None,
        })

    return items


@router.post("/{face_id}/confirm")
async def confirm_face(
    face_id: uuid.UUID,
    accept: bool = Query(..., description="True to confirm, False to reject"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Confirm or reject a pending face assignment."""
    result = await db.execute(
        select(Face)
        .join(Photo, Face.photo_id == Photo.id)
        .where(Face.id == face_id, Photo.user_id == user.id)
    )
    face = result.scalar_one_or_none()
    if not face:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Face not found")

    if accept:
        face.status = "confirmed"
    else:
        # Reject — remove from this person
        old_person_id = face.person_id
        face.person_id = None
        face.status = "rejected"

        # Update old person's face count
        if old_person_id:
            old_count = (await db.execute(
                select(func.count()).select_from(Face).where(Face.person_id == old_person_id)
            )).scalar() or 0
            old_person = (await db.execute(
                select(Person).where(Person.id == old_person_id)
            )).scalar_one_or_none()
            if old_person:
                old_person.face_count = old_count
                if old_count == 0:
                    await db.delete(old_person)

    return {
        "face_id": str(face.id),
        "status": face.status,
        "person_id": str(face.person_id) if face.person_id else None,
    }


@router.get("/confirm/count")
async def count_faces_to_confirm(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return the count of faces needing confirmation."""
    count = (await db.execute(
        select(func.count())
        .select_from(Face)
        .join(Photo, Face.photo_id == Photo.id)
        .where(Photo.user_id == user.id, Face.status == "pending")
    )).scalar() or 0
    return {"count": count}


@router.post("/cluster")
async def trigger_clustering(
    user: User = Depends(require_admin),
):
    """Run face clustering on all face embeddings (admin only). Runs synchronously."""
    from app.services.face_cluster import cluster_faces

    stats = cluster_faces(str(user.id))
    return {"message": "Clustering complete", **stats}


@router.post("/merge")
async def merge_face_clusters(
    body: MergePeopleRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Merge two face clusters: move all faces from person_id_merge into person_id_keep."""
    # Verify both people belong to user
    keep = (await db.execute(
        select(Person).where(Person.id == body.person_id_keep, Person.user_id == user.id)
    )).scalar_one_or_none()
    merge = (await db.execute(
        select(Person).where(Person.id == body.person_id_merge, Person.user_id == user.id)
    )).scalar_one_or_none()

    if not keep:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Keep person not found")
    if not merge:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Merge person not found")
    if keep.id == merge.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot merge a person with itself")

    # Move faces
    await db.execute(
        update(Face).where(Face.person_id == body.person_id_merge).values(person_id=body.person_id_keep)
    )

    # Update face count
    count = (await db.execute(
        select(func.count()).select_from(Face).where(Face.person_id == body.person_id_keep)
    )).scalar() or 0
    keep.face_count = count

    # Preserve name
    if not keep.name and merge.name:
        keep.name = merge.name

    await db.delete(merge)

    return {"message": "Merge complete", "person_id": str(keep.id), "face_count": count}
