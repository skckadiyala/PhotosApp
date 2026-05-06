"""
EXIF metadata extraction service.

Uses exifread to parse EXIF data and Pillow for image dimensions.
Extracts: date_taken, GPS lat/lng, camera_model, width, height, and more.
For video files (.mov, .mp4) uses a pure-Python QuickTime/MP4 atom parser to
extract creation date and dimensions from the mvhd/tkhd atoms.
"""
import logging
import os
import struct
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
    # Video
    ".mov": "video/quicktime",
    ".mp4": "video/mp4",
    ".m4v": "video/mp4",
    ".avi": "video/x-msvideo",
    ".mkv": "video/x-matroska",
    ".webm": "video/webm",
    ".3gp": "video/3gpp",
}


def extract_metadata(file_path: str) -> PhotoMetadata:
    """
    Extract EXIF metadata and image dimensions from a photo file.
    For video files, reads QuickTime/MP4 atoms directly.

    Args:
        file_path: Absolute path to the image file.

    Returns:
        PhotoMetadata with all available fields populated.
    """
    meta = PhotoMetadata()
    ext = os.path.splitext(file_path)[1].lower()
    meta.mime_type = _MIME_MAP.get(ext, "application/octet-stream")

    # --- Video files: parse QuickTime/MP4 atoms ---
    if meta.mime_type.startswith("video/"):
        vm = _extract_quicktime_metadata(file_path)
        # Prefer a date found in the filename (e.g. "Clips24-06-10_23-03.mov")
        # over the mvhd creation_time, which often reflects the import/copy date
        # rather than the original recording date when files are copied without
        # preserving metadata.
        fn_date = _parse_date_from_filename(os.path.basename(file_path))
        meta.taken_at = fn_date or vm.get("taken_at")
        meta.width = vm.get("width") or 0
        meta.height = vm.get("height") or 0
        if not meta.taken_at:
            try:
                meta.taken_at = datetime.utcfromtimestamp(os.path.getmtime(file_path))
            except OSError:
                pass
        return meta

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

    # Fall back to file mtime when EXIF carries no date — far better than
    # the DB created_at (scan date) that ends up grouping everything in 2026.
    if not meta.taken_at:
        try:
            meta.taken_at = datetime.utcfromtimestamp(os.path.getmtime(file_path))
        except OSError:
            pass

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


_FILENAME_DATE_PATTERNS = [
    # Clips24-06-10_23-03  →  2024-06-10 23:03
    (r"(\d{2})-(\d{2})-(\d{2})_(\d{2})-(\d{2})", "%y-%m-%d_%H-%M"),
    # VID_20240610_230347
    (r"VID_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})", "%Y%m%d_%H%M%S"),
    # 20240610_230347  or  20240610-230347
    (r"(\d{8})[_-](\d{6})", "%Y%m%d_%H%M%S"),
    # 2024-06-10 or 2024_06_10 anywhere in name
    (r"(\d{4})[_\-](\d{2})[_\-](\d{2})", "%Y-%m-%d"),
]


def _parse_date_from_filename(filename: str) -> datetime | None:
    """Try to extract a recording date from common video filename patterns."""
    import re
    stem = os.path.splitext(filename)[0]
    for pattern, fmt in _FILENAME_DATE_PATTERNS:
        m = re.search(pattern, stem)
        if m:
            try:
                if fmt == "%y-%m-%d_%H-%M":
                    # Groups: yy, mm, dd, HH, MM
                    s = f"{m.group(1)}-{m.group(2)}-{m.group(3)}_{m.group(4)}-{m.group(5)}"
                elif fmt == "%Y%m%d_%H%M%S" and len(m.groups()) == 6:
                    s = f"{m.group(1)}{m.group(2)}{m.group(3)}_{m.group(4)}{m.group(5)}{m.group(6)}"
                    fmt = "%Y%m%d_%H%M%S"
                elif fmt == "%Y%m%d_%H%M%S":
                    s = f"{m.group(1)}_{m.group(2)}"
                elif fmt == "%Y-%m-%d":
                    s = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
                else:
                    s = m.group(0)
                return datetime.strptime(s, fmt)
            except (ValueError, IndexError):
                continue
    return None


# ── QuickTime / MP4 pure-Python atom parser ──────────────────────────────────

# QuickTime epoch starts 1904-01-01; Unix epoch starts 1970-01-01.
_QT_EPOCH_OFFSET = 2082844800  # seconds


def _find_qt_atom(f, start: int, end: int, target: str):
    """
    Scan atoms within [start, end) for one matching *target*.
    Returns (data_start, atom_end) or None.
    """
    cur = start
    while cur < end:
        f.seek(cur)
        header = f.read(8)
        if len(header) < 8:
            break
        size = struct.unpack(">I", header[:4])[0]
        atom_type = header[4:8].decode("latin-1")
        data_start = cur + 8
        if size == 1:           # 64-bit largesize
            ext = f.read(8)
            if len(ext) < 8:
                break
            size = struct.unpack(">Q", ext)[0]
            data_start = cur + 16
        elif size == 0:         # atom extends to EOF
            size = end - cur
        if size < 8:
            break
        atom_end = cur + size
        if atom_type == target:
            return data_start, atom_end
        cur = atom_end
    return None


def _extract_quicktime_metadata(file_path: str) -> dict:
    """
    Extract creation time and video dimensions from a QuickTime/MP4 file by
    parsing the moov > mvhd (movie header) and moov > trak > tkhd atoms using
    only Python's built-in struct module.

    Returns a dict with optional keys: taken_at, width, height.
    """
    result: dict = {}
    try:
        file_size = os.path.getsize(file_path)
        with open(file_path, "rb") as f:
            moov = _find_qt_atom(f, 0, file_size, "moov")
            if moov is None:
                return result
            moov_data, moov_end = moov

            # ── mvhd: movie creation time ─────────────────────────────────
            mvhd = _find_qt_atom(f, moov_data, moov_end, "mvhd")
            if mvhd:
                f.seek(mvhd[0])
                version = struct.unpack("B", f.read(1))[0]
                f.read(3)  # flags
                if version == 0:
                    creation_time = struct.unpack(">I", f.read(4))[0]
                else:                    # version 1 uses 64-bit times
                    creation_time = struct.unpack(">Q", f.read(8))[0]
                unix_ts = creation_time - _QT_EPOCH_OFFSET
                if unix_ts > 0:
                    # Store as naïve datetime (consistent with EXIF dates)
                    result["taken_at"] = datetime.utcfromtimestamp(unix_ts)

            # ── trak > tkhd: video track dimensions ───────────────────────
            cur = moov_data
            while cur < moov_end:
                f.seek(cur)
                h = f.read(8)
                if len(h) < 8:
                    break
                sz = struct.unpack(">I", h[:4])[0]
                atype = h[4:8].decode("latin-1")
                ds = cur + 8
                if sz == 1:
                    ext = f.read(8)
                    sz = struct.unpack(">Q", ext)[0]
                    ds = cur + 16
                elif sz == 0:
                    sz = moov_end - cur
                if sz < 8:
                    break
                ae = cur + sz
                if atype == "trak":
                    tkhd = _find_qt_atom(f, ds, ae, "tkhd")
                    if tkhd:
                        f.seek(tkhd[0])
                        ver = struct.unpack("B", f.read(1))[0]
                        f.read(3)  # flags
                        # Skip to the width/height fields:
                        #   v0: create(4)+mod(4)+trackid(4)+reserved(4)+duration(4) = 20
                        #   v1: create(8)+mod(8)+trackid(4)+reserved(4)+duration(8) = 32
                        # Then: reserved[2](8)+layer(2)+altgroup(2)+volume(2)+reserved(2)+matrix(36) = 52
                        skip = (20 if ver == 0 else 32) + 52
                        f.read(skip)
                        raw = f.read(8)
                        if len(raw) == 8:
                            w_fp, h_fp = struct.unpack(">II", raw)
                            w, h = w_fp / 65536, h_fp / 65536
                            # Only keep the largest track (video vs audio stub)
                            if w > 0 and h > 0:
                                if result.get("width", 0) < int(round(w)):
                                    result["width"] = int(round(w))
                                    result["height"] = int(round(h))
                cur = ae

    except Exception:
        logger.debug("Could not extract QuickTime metadata from %s", file_path, exc_info=True)

    return result
