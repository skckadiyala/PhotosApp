"""
Thumbnail generation service.

Creates 3 sizes:
  - small:  200px (longest edge)
  - medium: 800px (longest edge)
  - large:  1600px (longest edge)

Thumbnails are stored in ./cache/thumbnails/{sm,md,lg}/{photo_uuid}.jpg
"""
import gc
import logging
import os
import subprocess
import tempfile

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

_VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".m4v", ".wmv", ".flv", ".webm", ".3gp", ".mts", ".m2ts"}


def _extract_video_frame(video_path: str) -> Image.Image:
    """Use ffmpeg to extract a representative frame from a video file."""
    probe = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path,
        ],
        capture_output=True, text=True, timeout=30,
    )
    try:
        duration = float(probe.stdout.strip())
        seek = min(duration * 0.1, 5.0)
    except (ValueError, TypeError):
        seek = 1.0

    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-ss", str(seek),
                "-i", video_path,
                "-vframes", "1",
                "-q:v", "2",
                tmp_path,
            ],
            capture_output=True, timeout=60, check=True,
        )
        frame = Image.open(tmp_path)
        frame.load()  # eagerly load pixels before the temp file is deleted
        return frame.copy()
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def generate_thumbnails(photo_id: str, source_path: str) -> dict[str, str]:
    """
    Generate sm/md/lg JPEG thumbnails for a photo or video.

    Args:
        photo_id: UUID string for the photo/video.
        source_path: Absolute path to the original file.

    Returns:
        Dict mapping size names to relative thumbnail paths, e.g.
        {"sm": "sm/<uuid>.jpg", "md": "md/<uuid>.jpg", "lg": "lg/<uuid>.jpg"}
    """
    ext = os.path.splitext(source_path)[1].lower()
    if ext in _VIDEO_EXTENSIONS:
        img = _extract_video_frame(source_path)
    else:
        raw = Image.open(source_path)
        raw.load()  # eagerly load pixels so the file handle can be released
        img = _auto_orient(raw)
        if img is not raw:
            raw.close()
            del raw

    results: dict[str, str] = {}
    try:
        for size_name, max_dim in SIZES.items():
            rel_path = os.path.join(size_name, f"{photo_id}.webp")
            abs_path = os.path.join(settings.thumbnails_dir, rel_path)
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)

            thumb = img.copy()
            thumb.thumbnail((max_dim, max_dim), Image.LANCZOS)
            thumb = thumb.convert("RGB")
            # WebP at quality=80 is ~40-50% smaller than JPEG/85 at equivalent perceptual quality
            thumb.save(abs_path, "WEBP", quality=80, method=4)
            thumb.close()
            del thumb

            results[size_name] = rel_path
    finally:
        img.close()
        del img
        gc.collect()

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
