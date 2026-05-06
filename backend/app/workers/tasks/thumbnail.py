import logging
import os

from app.config import get_settings
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)
settings = get_settings()


@celery_app.task(name="generate_thumbnails", bind=True, max_retries=3)
def generate_thumbnails(self, photo_id: str, file_path: str):
    """Generate sm/md/lg thumbnails for a photo or video and persist paths to DB."""
    from app.services.thumbnail import generate_thumbnails as _svc

    try:
        full_path = os.path.join(settings.photos_dir, file_path)
        if not os.path.isfile(full_path):
            logger.error("File not found: %s", full_path)
            return None

        results = _svc(photo_id, full_path)

        try:
            from app.core.database import get_sync_db
            from app.models.photo import Photo
            from sqlalchemy import select

            db = get_sync_db()
            try:
                photo = db.execute(select(Photo).where(Photo.id == photo_id)).scalar_one_or_none()
                if photo:
                    photo.thumb_sm = results.get("sm")
                    photo.thumb_md = results.get("md")
                    photo.thumb_lg = results.get("lg")
                    photo.is_processed = True
                    db.commit()
            finally:
                db.close()
        except Exception:
            logger.warning("Could not persist thumbnail paths for %s", photo_id, exc_info=True)

        return {"photo_id": photo_id, **{f"thumb_{k}": v for k, v in results.items()}}

    except Exception as exc:
        logger.exception("Thumbnail generation failed for %s", photo_id)
        raise self.retry(exc=exc, countdown=30)
