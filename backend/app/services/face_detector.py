"""
Face detection & embedding service.

Uses DeepFace with ArcFace for:
  1. Detecting faces in a photo (RetinaFace detector, opencv fallback)
  2. Extracting 512-d ArcFace embeddings
  3. Storing Face records in the database

ArcFace (trained on MS-Celeb-1M, ~10 M identities) produces significantly
more discriminative 512-d embeddings than the legacy dlib 128-d model,
leading to better person clustering.  Model weights are downloaded
automatically to ~/.deepface/weights/ on first use.

Run face processing for all unprocessed photos:
    python -m app.services.face_detector
"""
import logging
import os
import time

# DeepFace, NumPy and PIL are imported lazily (inside functions) so that
# TensorFlow and the ArcFace/RetinaFace model weights are NOT loaded into
# memory at server startup.  They are only pulled in the first time face
# detection is actually requested, saving ~2-3 GiB of RAM on idle servers.
from sqlalchemy import select

from app.config import get_settings
from app.core.database import get_sync_db
from app.models.face import Face
from app.models.photo import Photo

logger = logging.getLogger(__name__)
settings = get_settings()

# ArcFace model name (512-d L2-normalised embeddings).
RECOGNITION_MODEL = "ArcFace"

# Primary face detector.  RetinaFace is state-of-the-art and handles small /
# partially-occluded faces well.  We fall back to opencv if the model fails
# to load (e.g. network issues during first-run weight download).
DETECTOR_BACKEND = "retinaface"

# Minimum face bounding-box dimension.  RetinaFace is reliable down to ~30 px;
# 40 px avoids tiny false positives while keeping genuine small faces.
MIN_FACE_PX = 40

# Minimum RetinaFace detection confidence (0–1).  Detections below this are
# likely to be false positives (background textures, body parts).
# 0.75 keeps legitimate small/backlit/distant faces while filtering clear noise.
MIN_FACE_CONFIDENCE = 0.75

# Bounding-box aspect ratio guard: width/height must be within this range.
# Values outside indicate a sideways crop or partial edge detection.
MIN_ASPECT_RATIO = 0.45
MAX_ASPECT_RATIO = 2.20


def _represent_with_fallback(image) -> list | None:
    """
    Call DeepFace.represent with the primary detector and, if the primary
    backend finds no faces or fails to initialise, retry with opencv.

    Returns the raw DeepFace results list, or None if no faces were detected.
    """
    # Lazy import — keeps TensorFlow out of memory until face detection runs.
    from deepface import DeepFace  # noqa: PLC0415

    last_error = None
    for backend in (DETECTOR_BACKEND, "opencv"):
        try:
            results = DeepFace.represent(
                img_path=image,
                model_name=RECOGNITION_MODEL,
                detector_backend=backend,
                enforce_detection=True,
                align=True,
            )
            if results:
                return results
        except ValueError:
            # No face found by this backend — try the next one.
            last_error = "no face found"
        except Exception as exc:
            last_error = str(exc)
            if backend != "opencv":
                logger.debug(
                    "detector_backend=%s failed (%s), falling back to opencv",
                    backend, exc,
                )
            else:
                logger.warning("opencv detection also failed: %s", exc)
    logger.debug("No faces detected after all backends (%s)", last_error)
    return None


def detect_faces_in_photo(photo_path: str) -> list[dict]:
    """
    Detect faces in a single photo.

    Args:
        photo_path: Absolute path to the image file.

    Returns:
        List of dicts with keys:
          - location: {top, right, bottom, left}
          - embedding: 512-d numpy array (L2-normalised ArcFace embedding)
    """
    # Apply EXIF orientation so portrait photos are upright before detection.
    import numpy as np  # noqa: PLC0415
    from PIL import Image, ImageOps  # noqa: PLC0415

    pil_img = Image.open(photo_path)
    pil_img = ImageOps.exif_transpose(pil_img).convert("RGB")
    image = np.array(pil_img)

    results_raw = _represent_with_fallback(image)
    if not results_raw:
        return []

    faces = []
    for r in results_raw:
        area = r["facial_area"]
        x, y, w, h = area["x"], area["y"], area["w"], area["h"]

        # Skip detections that are too small to be reliable.
        if w < MIN_FACE_PX or h < MIN_FACE_PX:
            continue

        # Skip detections with extreme aspect ratios (partial/cropped faces).
        aspect = w / h if h > 0 else 0
        if not (MIN_ASPECT_RATIO <= aspect <= MAX_ASPECT_RATIO):
            logger.debug("Skipping face: aspect ratio %.2f out of range", aspect)
            continue

        # Skip low-confidence detections (RetinaFace returns a score 0–1).
        confidence = r.get("face_confidence", 1.0)
        if confidence < MIN_FACE_CONFIDENCE:
            logger.debug("Skipping face: confidence %.3f < %.2f", confidence, MIN_FACE_CONFIDENCE)
            continue

        # facial_area uses (x=left, y=top, w, h); convert to the stored format.
        faces.append({
            "location": {"top": y, "right": x + w, "bottom": y + h, "left": x},
            "embedding": np.array(r["embedding"]),
            "confidence": confidence,
        })

    return faces


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
                confidence=face_data.get("confidence", 1.0),
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
        query = (
            select(Photo)
            .outerjoin(Face, Photo.id == Face.photo_id)
            .where(Face.id.is_(None))
            .where(~Photo.mime_type.like("video/%"))
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


def reprocess_faces_for_filenames(filenames: list[str]) -> dict:
    """
    Purge existing Face records for the given filenames then re-run
    face detection on those photos.  Use this to restore real faces that
    were accidentally purged, or to reprocess a specific image after a
    detection-parameter change.

    Args:
        filenames: List of image filenames, e.g. ["IMG_2367.jpeg"]

    Returns:
        dict: {matched_photos, old_faces_deleted, new_faces_added, errors}
    """
    db = get_sync_db()
    stats = {"matched_photos": 0, "old_faces_deleted": 0, "new_faces_added": 0, "errors": 0}
    lower_names = [n.lower() for n in filenames]

    try:
        all_photos = db.execute(select(Photo)).scalars().all()
        targets = [
            p for p in all_photos
            if any(p.file_path.lower().endswith(name) for name in lower_names)
        ]

        if not targets:
            logger.warning("No photos matched filenames: %s", filenames)
            return stats

        stats["matched_photos"] = len(targets)

        from sqlalchemy import delete as sql_delete
        result = db.execute(sql_delete(Face).where(Face.photo_id.in_([p.id for p in targets])))
        stats["old_faces_deleted"] = result.rowcount
        db.commit()

        for photo in targets:
            abs_path = os.path.join(settings.photos_dir, photo.file_path)
            if not os.path.isfile(abs_path):
                logger.warning("Photo file missing: %s", abs_path)
                stats["errors"] += 1
                continue
            try:
                n = process_photo_faces(str(photo.id), abs_path, db_session=db)
                stats["new_faces_added"] += n
                logger.info("Re-detected %d face(s) in %s", n, photo.file_path)
            except Exception:
                logger.error("Failed to reprocess %s", photo.file_path, exc_info=True)
                stats["errors"] += 1

    except Exception:
        db.rollback()
        logger.error("Failed to reprocess files %s", filenames, exc_info=True)
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

    reprocess_file_p = sub.add_parser("reprocess-file", help="Re-run detection on specific filenames (purge then re-detect)")
    reprocess_file_p.add_argument("filenames", nargs="+", help="Image filenames to reprocess (e.g. IMG_2367.jpeg)")

    args = parser.parse_args()

    if args.cmd == "purge":
        stats = purge_faces_for_filenames(args.filenames)
        print(f"\nPurge results: {stats}")
    elif args.cmd == "reprocess-file":
        stats = reprocess_faces_for_filenames(args.filenames)
        print(f"\nReprocess-file results: {stats}")
    elif args.cmd == "reprocess":
        stats = reprocess_all_photos()
        print(f"\nReprocess results: {stats}")
    else:
        stats = process_all_photos()
        print(f"\nFace detection results: {stats}")


if __name__ == "__main__":
    main()
