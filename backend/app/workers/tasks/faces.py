import logging
import os

from app.config import get_settings
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)
settings = get_settings()


VIDEO_EXTENSIONS = {'.mp4', '.mov', '.avi', '.mkv', '.m4v', '.3gp', '.webm', '.mts', '.m2ts'}


@celery_app.task(name="detect_faces", bind=True, max_retries=2)
def detect_faces(self, photo_id: str, file_path: str):
    """Detect faces and persist embeddings for a single photo (images only)."""
    ext = os.path.splitext(file_path)[1].lower()
    if ext in VIDEO_EXTENSIONS:
        logger.debug("Skipping face detection on video %s", file_path)
        return None

    try:
        full_path = os.path.join(settings.photos_dir, file_path)
        if not os.path.isfile(full_path):
            logger.error("Photo file not found: %s", full_path)
            return None

        from app.services.face_detector import process_photo_faces
        n_faces = process_photo_faces(photo_id, full_path)
        logger.info("Detected %d face(s) in photo %s", n_faces, photo_id)
        return {"photo_id": photo_id, "faces_detected": n_faces}

    except Exception as exc:
        logger.exception("Face detection failed for %s", photo_id)
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(name="run_bulk_face_scan", bind=True)
def run_bulk_face_scan(self, user_id: str):
    """Detect faces on all unprocessed photos, then cluster into people.

    Runs entirely inside the face_worker container so the backend process
    stays free for API requests.
    """
    from app.services.face_detector import process_all_photos
    from app.services.face_cluster import cluster_faces

    logger.info("Bulk face scan starting for user %s", user_id)
    stats = process_all_photos(user_id=user_id)
    logger.info("Bulk face scan complete: %s", stats)

    if stats.get("total_faces", 0) > 0:
        cluster_stats = cluster_faces(user_id)
        logger.info("Face clustering complete: %s", cluster_stats)

    return stats
