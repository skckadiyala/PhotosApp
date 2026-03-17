"""
EXIF metadata extraction service.

Uses exifread to parse EXIF data and Pillow for image dimensions.
Extracts: date_taken, GPS lat/lng, camera_model, width, height, and more.
"""
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime

import exifread
from PIL import Image

logger = logging.getLogger(__name__)

# Register HEIF opener so Pillow can read .heic/.heif
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    logger.debug("pillow-heif not installed; HEIC support disabled")


@dataclass
class PhotoMetadata:
    """Extracted metadata from a photo file."""
    width: int = 0
    height: int = 0
    taken_at: datetime | None = None
    camera_make: str | None = None
    camera_model: str | None = None
    lens_model: str | None = None
    f_number: float | None = None
    exposure_time: str | None = None
    iso: int | None = None
    focal_length: float | None = None
    orientation: int | None = None
    gps_latitude: float | None = None
    gps_longitude: float | None = None
    mime_type: str = "image/jpeg"


# Extension → MIME mapping
_MIME_MAP = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
    ".webp": "image/webp",
    ".tiff": "image/tiff",
    ".tif": "image/tiff",
    ".heic": "image/heic",
    ".heif": "image/heif",
    ".raw": "image/x-raw",
    ".cr2": "image/x-canon-cr2",
    ".nef": "image/x-nikon-nef",
    ".arw": "image/x-sony-arw",
    ".dng": "image/x-adobe-dng",
}


def extract_metadata(file_path: str) -> PhotoMetadata:
    """
    Extract EXIF metadata and image dimensions from a photo file.

    Args:
        file_path: Absolute path to the image file.

    Returns:
        PhotoMetadata with all available fields populated.
    """
    meta = PhotoMetadata()
    ext = os.path.splitext(file_path)[1].lower()
    meta.mime_type = _MIME_MAP.get(ext, "application/octet-stream")

    # --- Image dimensions via Pillow ---
    try:
        with Image.open(file_path) as img:
            meta.width, meta.height = img.size
    except Exception:
        logger.debug("Could not read image dimensions: %s", file_path)

    # --- EXIF via exifread ---
    try:
        with open(file_path, "rb") as f:
            tags = exifread.process_file(f, details=False)
    except Exception:
        logger.debug("Could not read EXIF: %s", file_path)
        return meta

    meta.camera_make = _get_str(tags, "Image Make")
    meta.camera_model = _get_str(tags, "Image Model")
    meta.lens_model = _get_str(tags, "EXIF LensModel")
    meta.f_number = _get_rational(tags, "EXIF FNumber")
    meta.exposure_time = _get_str(tags, "EXIF ExposureTime")
    meta.iso = _get_int(tags, "EXIF ISOSpeedRatings")
    meta.focal_length = _get_rational(tags, "EXIF FocalLength")
    meta.orientation = _get_int(tags, "Image Orientation")
    meta.taken_at = _get_datetime(tags)

    # GPS
    gps = _extract_gps(tags)
    if gps:
        meta.gps_latitude = gps[0]
        meta.gps_longitude = gps[1]

    # Correct width/height based on orientation if needed
    if meta.orientation in (5, 6, 7, 8) and meta.width and meta.height:
        meta.width, meta.height = meta.height, meta.width

    return meta


# ── Private helpers ──────────────────────────────────────────

def _get_str(tags: dict, key: str) -> str | None:
    val = tags.get(key)
    return str(val).strip() if val else None


def _get_int(tags: dict, key: str) -> int | None:
    val = tags.get(key)
    if val:
        try:
            return int(str(val))
        except (ValueError, TypeError):
            pass
    return None


def _get_rational(tags: dict, key: str) -> float | None:
    val = tags.get(key)
    if val:
        try:
            r = val.values[0]
            if r.den and r.den != 0:
                return float(r.num) / float(r.den)
        except (AttributeError, IndexError, ZeroDivisionError):
            pass
    return None


def _get_datetime(tags: dict) -> datetime | None:
    for key in ["EXIF DateTimeOriginal", "EXIF DateTimeDigitized", "Image DateTime"]:
        val = tags.get(key)
        if val:
            try:
                return datetime.strptime(str(val), "%Y:%m:%d %H:%M:%S")
            except ValueError:
                continue
    return None


def _extract_gps(tags: dict) -> tuple[float, float] | None:
    """Extract GPS coordinates as (latitude, longitude), or None."""
    lat_tag = tags.get("GPS GPSLatitude")
    lat_ref = tags.get("GPS GPSLatitudeRef")
    lng_tag = tags.get("GPS GPSLongitude")
    lng_ref = tags.get("GPS GPSLongitudeRef")

    if not all([lat_tag, lat_ref, lng_tag, lng_ref]):
        return None

    try:
        lat = _dms_to_decimal(lat_tag.values, str(lat_ref))
        lng = _dms_to_decimal(lng_tag.values, str(lng_ref))
        return (lat, lng)
    except Exception:
        return None


def _dms_to_decimal(dms_values: list, ref: str) -> float:
    """Convert GPS DMS (degrees, minutes, seconds) to decimal degrees."""
    d = float(dms_values[0].num) / float(dms_values[0].den) if dms_values[0].den else 0
    m = float(dms_values[1].num) / float(dms_values[1].den) if dms_values[1].den else 0
    s = float(dms_values[2].num) / float(dms_values[2].den) if dms_values[2].den else 0

    decimal = d + m / 60.0 + s / 3600.0
    if ref in ("S", "W"):
        decimal = -decimal
    return decimal
