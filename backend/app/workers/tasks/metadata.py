import logging
import os
from datetime import datetime

import exifread

from app.config import get_settings
from app.utils.geo import dms_to_decimal
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)
settings = get_settings()


@celery_app.task(name="extract_metadata", bind=True, max_retries=3)
def extract_metadata(self, photo_id: str, file_path: str):
    """Extract EXIF metadata from a photo."""
    try:
        full_path = os.path.join(settings.photos_dir, file_path)
        if not os.path.isfile(full_path):
            logger.error("Photo file not found: %s", full_path)
            return None

        with open(full_path, "rb") as f:
            tags = exifread.process_file(f, details=False)

        metadata = {
            "photo_id": photo_id,
            "camera_make": _get_tag(tags, "Image Make"),
            "camera_model": _get_tag(tags, "Image Model"),
            "lens_model": _get_tag(tags, "EXIF LensModel"),
            "f_number": _get_rational(tags, "EXIF FNumber"),
            "exposure_time": _get_tag(tags, "EXIF ExposureTime"),
            "iso": _get_int(tags, "EXIF ISOSpeedRatings"),
            "focal_length": _get_rational(tags, "EXIF FocalLength"),
            "orientation": _get_int(tags, "Image Orientation"),
            "taken_at": _get_datetime(tags),
        }

        # GPS coordinates
        gps = _extract_gps(tags)
        if gps:
            metadata["latitude"] = gps["latitude"]
            metadata["longitude"] = gps["longitude"]
            metadata["altitude"] = gps.get("altitude")

        return metadata

    except Exception as exc:
        logger.exception("Metadata extraction failed for %s", photo_id)
        raise self.retry(exc=exc, countdown=30)


def _get_tag(tags: dict, key: str) -> str | None:
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
            return float(r.num) / float(r.den) if r.den else None
        except (AttributeError, IndexError, ZeroDivisionError):
            pass
    return None


def _get_datetime(tags: dict) -> str | None:
    for key in ["EXIF DateTimeOriginal", "EXIF DateTimeDigitized", "Image DateTime"]:
        val = tags.get(key)
        if val:
            try:
                dt = datetime.strptime(str(val), "%Y:%m:%d %H:%M:%S")
                return dt.isoformat()
            except ValueError:
                continue
    return None


def _extract_gps(tags: dict) -> dict | None:
    lat_tag = tags.get("GPS GPSLatitude")
    lat_ref = tags.get("GPS GPSLatitudeRef")
    lng_tag = tags.get("GPS GPSLongitude")
    lng_ref = tags.get("GPS GPSLongitudeRef")

    if not all([lat_tag, lat_ref, lng_tag, lng_ref]):
        return None

    try:
        lat = dms_to_decimal(lat_tag.values, str(lat_ref))
        lng = dms_to_decimal(lng_tag.values, str(lng_ref))
        result = {"latitude": lat, "longitude": lng}

        alt_tag = tags.get("GPS GPSAltitude")
        if alt_tag:
            try:
                r = alt_tag.values[0]
                result["altitude"] = float(r.num) / float(r.den) if r.den else None
            except (AttributeError, IndexError, ZeroDivisionError):
                pass

        return result
    except Exception:
        return None
