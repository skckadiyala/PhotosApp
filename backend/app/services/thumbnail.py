"""
Thumbnail generation service.

Creates 3 sizes:
  - small:  200px (longest edge)
  - medium: 800px (longest edge)
  - large:  1600px (longest edge)

Thumbnails are stored in ./cache/thumbnails/{sm,md,lg}/{photo_uuid}.jpg
"""
import logging
import os

from PIL import Image, ExifTags

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Register HEIF opener
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    pass

SIZES = {
    "sm": settings.thumb_sm,   # 200
    "md": settings.thumb_md,   # 800
    "lg": settings.thumb_lg,   # 1600
}


def generate_thumbnails(photo_id: str, source_path: str) -> dict[str, str]:
    """
    Generate sm/md/lg JPEG thumbnails for a photo.

    Args:
        photo_id: UUID string for the photo.
        source_path: Absolute path to the original image file.

    Returns:
        Dict mapping size names to relative thumbnail paths, e.g.
        {"sm": "sm/<uuid>.jpg", "md": "md/<uuid>.jpg", "lg": "lg/<uuid>.jpg"}
    """
    img = Image.open(source_path)
    img = _auto_orient(img)

    results: dict[str, str] = {}
    for size_name, max_dim in SIZES.items():
        rel_path = os.path.join(size_name, f"{photo_id}.jpg")
        abs_path = os.path.join(settings.thumbnails_dir, rel_path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)

        thumb = img.copy()
        thumb.thumbnail((max_dim, max_dim), Image.LANCZOS)
        thumb = thumb.convert("RGB")
        thumb.save(abs_path, "JPEG", quality=85, optimize=True)

        results[size_name] = rel_path
        logger.debug("Generated %s thumbnail: %s", size_name, rel_path)

    logger.info("Generated thumbnails for photo %s", photo_id)
    return results


def _auto_orient(img: Image.Image) -> Image.Image:
    """Auto-rotate image based on EXIF orientation tag."""
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
