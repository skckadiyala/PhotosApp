"""
Face detection & embedding service.

Uses the `face_recognition` library (dlib-based) to:
  1. Detect faces in a photo
  2. Extract 128-d face embeddings
  3. Store Face records in the database

Run face processing for all unprocessed photos:
    python -m app.services.face_detector
"""
import logging
import os
import time

import face_recognition
import numpy as np
from PIL import Image, ImageOps
from sqlalchemy import select

from app.config import get_settings
from app.core.database import get_sync_db
from app.models.face import Face
from app.models.photo import Photo

logger = logging.getLogger(__name__)
settings = get_settings()

# Minimum face bounding-box dimension in pixels.
# Detections smaller than this are almost always false positives caused by
# texture patterns in landscapes (rocks, foliage, cloud formations, etc.).
MIN_FACE_PX = 80


def _has_valid_landmarks(lm: dict) -> bool:
    """Return True only when both eyes are detectable — the strongest signal
    that a detected region is an actual face rather than a landscape pattern."""
    return "left_eye" in lm and "right_eye" in lm


def detect_faces_in_photo(photo_path: str) -> list[dict]:
    """
    Detect faces in a single photo.

    Args:
        photo_path: Absolute path to the image file.

    Returns:
        List of dicts with keys: location (top, right, bottom, left), embedding (128-d numpy array)
    """
    # Load image and apply EXIF orientation so portrait photos are upright.
    # face_recognition.load_image_file() does NOT respect EXIF rotation,
    # causing sideways faces to be missed entirely.
    pil_img = Image.open(photo_path)
    pil_img = ImageOps.exif_transpose(pil_img).convert("RGB")
    image = np.array(pil_img)

    # Use upsample=1 only.  The previous upsample=2 fallback was far too
    # aggressive: it detects texture patterns in landscapes (rocks, mountains,
    # foliage) as faces, producing the false positives seen in IMG_0638.jpeg
    # and DSC_8301.JPG.
    locations = face_recognition.face_locations(image, model="hog", number_of_times_to_upsample=1)
    if not locations:
        return []

    # Filter 1 — minimum size.
    # Tiny bounding boxes are virtually always texture false positives.
    locations = [
        loc for loc in locations
        if (loc[2] - loc[0]) >= MIN_FACE_PX and (loc[1] - loc[3]) >= MIN_FACE_PX
    ]
    if not locations:
        return []

    # Filter 2 — landmark validation.
    # Real faces have detectable eyes, nose and mouth; landscape patterns do not.
    # We require at least both eyes to be present before accepting a detection.
    landmarks_list = face_recognition.face_landmarks(image, face_locations=locations)
    locations = [
        loc for loc, lm in zip(locations, landmarks_list)
        if _has_valid_landmarks(lm)
    ]
    if not locations:
        return []

    # Compute 128-d embeddings for each face.
    # num_jitters=3 re-samples each face multiple times and averages,
    # producing more stable embeddings for better clustering.
    encodings = face_recognition.face_encodings(image, known_face_locations=locations, num_jitters=3)

    results = []
    for loc, enc in zip(locations, encodings):
        top, right, bottom, left = loc
        results.append({
            "location": {"top": top, "right": right, "bottom": bottom, "left": left},
            "embedding": enc,
        })

    return results


def process_photo_faces(photo_id: str, photo_path: str, db_session=None) -> int:
    """
    Detect faces in a photo and store them in the database.

    Args:
        photo_id: UUID string of the photo.
        photo_path: Absolute path to the image on disk.
        db_session: Optional existing sync DB session.

    Returns:
        Number of faces detected and stored.
    """
    own_session = db_session is None
    db = db_session or get_sync_db()

    try:
        faces = detect_faces_in_photo(photo_path)
        if not faces:
            logger.debug("No faces in photo %s", photo_id)
            return 0

        for face_data in faces:
            loc = face_data["location"]
            embedding = face_data["embedding"]

            face = Face(
                photo_id=photo_id,
                bbox_top=loc["top"],
                bbox_right=loc["right"],
                bbox_bottom=loc["bottom"],
                bbox_left=loc["left"],
                embedding=embedding.tolist(),
                confidence=1.0,
            )
            db.add(face)

        if own_session:
            db.commit()

        logger.info("Detected %d face(s) in photo %s", len(faces), photo_id)
        return len(faces)

    except Exception:
        logger.error("Face detection failed for photo %s", photo_id, exc_info=True)
        if own_session:
            db.rollback()
        return 0
    finally:
        if own_session:
            db.close()


def process_all_photos(user_id: str | None = None) -> dict:
    """
    Run face detection on all photos that haven't been processed for faces yet.

    Processes photos that have no Face records.

    Args:
        user_id: Optional user_id filter.

    Returns:
        Stats dict: {total_processed, total_faces, errors}
    """
    t0 = time.time()
    db = get_sync_db()
    stats = {"total_processed": 0, "total_faces": 0, "errors": 0}

    try:
        # Find photos with no faces detected yet
        # Left join faces and filter where face.id IS NULL
        from sqlalchemy import and_, outerjoin
        from sqlalchemy.orm import aliased

        query = (
            select(Photo)
            .outerjoin(Face, Photo.id == Face.photo_id)
            .where(Face.id.is_(None))
        )
        if user_id:
            query = query.where(Photo.user_id == user_id)

        result = db.execute(query)
        photos = list(result.scalars().all())

        logger.info("Found %d photos without face detection", len(photos))

        for i, photo in enumerate(photos, 1):
            abs_path = os.path.join(settings.photos_dir, photo.file_path)
            if not os.path.isfile(abs_path):
                logger.warning("Photo file missing: %s", abs_path)
                stats["errors"] += 1
                continue

            try:
                n_faces = process_photo_faces(str(photo.id), abs_path, db_session=db)
                stats["total_faces"] += n_faces
                stats["total_processed"] += 1

                if i % 10 == 0:
                    db.commit()
                    logger.info("[%d/%d] Processed, %d faces so far", i, len(photos), stats["total_faces"])
            except Exception:
                stats["errors"] += 1
                logger.error("Error processing photo %s", photo.id, exc_info=True)
                db.rollback()

        db.commit()
    finally:
        db.close()

    elapsed = time.time() - t0
    logger.info(
        "Face detection complete in %.1fs: %d photos, %d faces, %d errors",
        elapsed, stats["total_processed"], stats["total_faces"], stats["errors"],
    )
    return stats


def reprocess_all_photos(user_id: str | None = None) -> dict:
    """
    Delete ALL existing Face records and re-detect faces for every photo.
    Use this after upgrading detection parameters (e.g. num_jitters).
    """
    t0 = time.time()
    db = get_sync_db()
    stats = {"total_processed": 0, "total_faces": 0, "errors": 0, "old_faces_deleted": 0}

    try:
        # First, delete all existing faces (cascading from Person is handled by cluster step)
        from sqlalchemy import delete as sql_delete

        if user_id:
            photo_ids = db.execute(
                select(Photo.id).where(Photo.user_id == user_id)
            ).scalars().all()
            if photo_ids:
                result = db.execute(
                    sql_delete(Face).where(Face.photo_id.in_(photo_ids))
                )
                stats["old_faces_deleted"] = result.rowcount
        else:
            result = db.execute(sql_delete(Face))
            stats["old_faces_deleted"] = result.rowcount

        db.commit()
        logger.info("Deleted %d old face records for reprocessing", stats["old_faces_deleted"])

        # Now detect on all photos
        query = select(Photo)
        if user_id:
            query = query.where(Photo.user_id == user_id)

        photos = list(db.execute(query).scalars().all())
        logger.info("Re-processing faces for %d photos", len(photos))

        for i, photo in enumerate(photos, 1):
            abs_path = os.path.join(settings.photos_dir, photo.file_path)
            if not os.path.isfile(abs_path):
                stats["errors"] += 1
                continue
            try:
                n_faces = process_photo_faces(str(photo.id), abs_path, db_session=db)
                stats["total_faces"] += n_faces
                stats["total_processed"] += 1
                if i % 10 == 0:
                    db.commit()
                    logger.info("[%d/%d] Re-processed, %d faces so far", i, len(photos), stats["total_faces"])
            except Exception:
                stats["errors"] += 1
                logger.error("Error re-processing photo %s", photo.id, exc_info=True)
                db.rollback()

        db.commit()
    finally:
        db.close()

    elapsed = time.time() - t0
    logger.info(
        "Face re-detection complete in %.1fs: %d photos, %d faces, %d errors",
        elapsed, stats["total_processed"], stats["total_faces"], stats["errors"],
    )
    return stats


def purge_faces_for_filenames(filenames: list[str]) -> dict:
    """
    Delete all Face records that belong to photos whose file_path ends with
    any of the given filenames (case-insensitive).

    Use this to clean up false-positive detections on specific images, e.g.:
        purge_faces_for_filenames(["IMG_0638.jpeg", "DSC_8301.JPG"])

    Returns:
        dict: {deleted_faces, matched_photos}
    """
    from sqlalchemy import delete as sql_delete

    db = get_sync_db()
    stats = {"deleted_faces": 0, "matched_photos": 0}
    lower_names = [n.lower() for n in filenames]

    try:
        all_photos = db.execute(select(Photo)).scalars().all()
        target_ids = [
            p.id for p in all_photos
            if any(p.file_path.lower().endswith(name) for name in lower_names)
        ]

        if not target_ids:
            logger.warning("No photos matched filenames: %s", filenames)
            return stats

        stats["matched_photos"] = len(target_ids)
        result = db.execute(sql_delete(Face).where(Face.photo_id.in_(target_ids)))
        stats["deleted_faces"] = result.rowcount

        # Delete Person records that are now empty AND unnamed.
        # Named clusters are kept even if temporarily empty.
        from app.models.person import Person as PersonModel
        orphaned = db.execute(
            select(PersonModel).where(
                PersonModel.name.is_(None),
                ~PersonModel.id.in_(select(Face.person_id).where(Face.person_id.isnot(None))),
            )
        ).scalars().all()
        for p in orphaned:
            db.delete(p)
        stats["orphaned_clusters_deleted"] = len(orphaned)

        db.commit()
        logger.info(
            "Purged %d false-positive face record(s) from %d photo(s), deleted %d orphaned cluster(s): %s",
            stats["deleted_faces"], stats["matched_photos"], stats["orphaned_clusters_deleted"], filenames,
        )
    except Exception:
        db.rollback()
        logger.error("Failed to purge faces for %s", filenames, exc_info=True)
        raise
    finally:
        db.close()

    return stats


def main():
    """CLI entry point for face detection."""
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    from app.models import Base
    from app.core.database import sync_engine
    Base.metadata.create_all(bind=sync_engine)

    parser = argparse.ArgumentParser(description="Face detection utilities")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("detect", help="Detect faces in all unprocessed photos")
    sub.add_parser("reprocess", help="Delete all faces and re-detect from scratch")

    purge_p = sub.add_parser("purge", help="Remove false-positive faces for specific filenames")
    purge_p.add_argument("filenames", nargs="+", help="Image filenames to purge (e.g. IMG_0638.jpeg)")

    args = parser.parse_args()

    if args.cmd == "purge":
        stats = purge_faces_for_filenames(args.filenames)
        print(f"\nPurge results: {stats}")
    elif args.cmd == "reprocess":
        stats = reprocess_all_photos()
        print(f"\nReprocess results: {stats}")
    else:
        stats = process_all_photos()
        print(f"\nFace detection results: {stats}")


if __name__ == "__main__":
    main()
