import logging
import os

from PIL import Image

from app.config import get_settings
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)
settings = get_settings()


@celery_app.task(name="generate_thumbnails", bind=True, max_retries=3)
def generate_thumbnails(self, photo_id: str, file_path: str):
    """Generate sm/md/lg thumbnails for a photo."""
    try:
        full_path = os.path.join(settings.photos_dir, file_path)
        if not os.path.isfile(full_path):
            logger.error("Photo file not found: %s", full_path)
            return None

        img = Image.open(full_path)
        img = _auto_orient(img)

        results = {}
        for size_name, max_dim in [("sm", settings.thumb_sm), ("md", settings.thumb_md), ("lg", settings.thumb_lg)]:
            thumb_rel = os.path.join(size_name, f"{photo_id}.jpg")
            thumb_path = os.path.join(settings.thumbnails_dir, thumb_rel)
            os.makedirs(os.path.dirname(thumb_path), exist_ok=True)

            thumb = img.copy()
            thumb.thumbnail((max_dim, max_dim), Image.LANCZOS)
            thumb = thumb.convert("RGB")
            thumb.save(thumb_path, "JPEG", quality=85, optimize=True)

            results[f"thumb_{size_name}"] = thumb_rel
            logger.info("Generated %s thumbnail: %s", size_name, thumb_rel)

        return {"photo_id": photo_id, **results}

    except Exception as exc:
        logger.exception("Thumbnail generation failed for %s", photo_id)
        raise self.retry(exc=exc, countdown=30)


def _auto_orient(img: Image.Image) -> Image.Image:
    """Auto-rotate image based on EXIF orientation."""
    from PIL import ExifTags

    try:
        exif = img.getexif()
        orientation_key = next(k for k, v in ExifTags.TAGS.items() if v == "Orientation")
        orientation = exif.get(orientation_key)

        rotations = {3: 180, 6: 270, 8: 90}
        if orientation in rotations:
            img = img.rotate(rotations[orientation], expand=True)
    except (StopIteration, AttributeError, KeyError):
        pass
    return img
