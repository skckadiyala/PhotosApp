"""
Recursive photo scanner.

Walks PHOTOS_DIR, discovers image files, and for each:
  1. Computes SHA-256 hash (dedup)
  2. Extracts EXIF metadata
  3. Generates 3 thumbnail sizes
  4. Inserts a Photo row into PostgreSQL

Can be run as:
    python -m app.services.scanner          # full scan
    python -m app.services.scanner --dry    # dry-run (list files only)
"""
import hashlib
import logging
import os
import sys
import time

from sqlalchemy import select

from app.config import get_settings
from app.core.database import get_sync_db, sync_engine
from app.models import Base
from app.models.photo import Photo
from app.models.user import User
from app.services.exif import extract_metadata
from app.services.thumbnail import generate_thumbnails

logger = logging.getLogger(__name__)
settings = get_settings()


def compute_file_hash(path: str, chunk_size: int = 65536) -> str:
    """Compute SHA-256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            sha256.update(chunk)
    return sha256.hexdigest()


def discover_files(root: str) -> list[str]:
    """Recursively find all supported image files under root."""
    found: list[str] = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for fname in filenames:
            ext = os.path.splitext(fname)[1].lower()
            if ext in settings.supported_extensions:
                found.append(os.path.join(dirpath, fname))
    found.sort()
    return found


def scan_library(user_id: str, dry_run: bool = False) -> dict:
    """
    Scan the photos directory and index all photos into the database.

    Args:
        user_id: UUID string of the user who owns these photos.
        dry_run: If True, only list files without indexing.

    Returns:
        Stats dict: {total_found, new_indexed, skipped_existing, errors}
    """
    photos_dir = settings.photos_dir
    if not os.path.isdir(photos_dir):
        logger.error("Photos directory does not exist: %s", photos_dir)
        return {"error": f"Directory not found: {photos_dir}"}

    logger.info("Scanning %s for photos...", photos_dir)
    t0 = time.time()

    files = discover_files(photos_dir)
    total_found = len(files)
    logger.info("Found %d image files", total_found)

    if dry_run:
        for f in files:
            print(os.path.relpath(f, photos_dir))
        return {"total_found": total_found, "dry_run": True}

    stats = {"total_found": total_found, "new_indexed": 0, "skipped_existing": 0, "errors": 0}
    db = get_sync_db()

    try:
        # Pre-load existing file paths AND hashes in a single query for fast
        # O(1) dedup.  Checking path first avoids reading any file from disk
        # for photos that are already indexed — critical for 100K+ libraries.
        existing_paths: set[str] = set()
        existing_hashes: set[str] = set()
        result = db.execute(
            select(Photo.file_path, Photo.file_hash).where(Photo.user_id == user_id)
        )
        for row in result:
            existing_paths.add(row[0])
            existing_hashes.add(row[1])
        logger.info("Found %d existing photos in database", len(existing_paths))

        for i, abs_path in enumerate(files, 1):
            rel_path = os.path.relpath(abs_path, photos_dir)
            try:
                # Fast path: file path already known — skip without any disk I/O.
                if rel_path in existing_paths:
                    stats["skipped_existing"] += 1
                    continue

                # New path — compute hash to detect renamed/moved duplicates.
                file_hash = compute_file_hash(abs_path)

                # Skip if already indexed under a different path (moved file).
                if file_hash in existing_hashes:
                    stats["skipped_existing"] += 1
                    if i % 100 == 0:
                        logger.info("[%d/%d] Skipping (moved/renamed): %s", i, total_found, rel_path)
                    continue

                # Extract EXIF metadata
                meta = extract_metadata(abs_path)

                # Build photo record
                photo = Photo(
                    file_path=rel_path,
                    file_name=os.path.basename(abs_path),
                    file_hash=file_hash,
                    file_size=os.path.getsize(abs_path),
                    mime_type=meta.mime_type,
                    width=meta.width or None,
                    height=meta.height or None,
                    taken_at=meta.taken_at,
                    camera_make=meta.camera_make,
                    camera_model=meta.camera_model,
                    lens_model=meta.lens_model,
                    f_number=meta.f_number,
                    exposure_time=meta.exposure_time,
                    iso=meta.iso,
                    focal_length=meta.focal_length,
                    orientation=meta.orientation,
                    gps_latitude=meta.gps_latitude,
                    gps_longitude=meta.gps_longitude,
                    user_id=user_id,
                    is_processed=False,
                )
                db.add(photo)
                db.flush()  # get photo.id

                # Generate thumbnails
                photo_id_str = str(photo.id)
                try:
                    thumbs = generate_thumbnails(photo_id_str, abs_path)
                    photo.thumb_sm = thumbs.get("sm")
                    photo.thumb_md = thumbs.get("md")
                    photo.thumb_lg = thumbs.get("lg")
                    photo.is_processed = True
                except Exception:
                    logger.warning("Thumbnail generation failed for %s", rel_path, exc_info=True)

                existing_hashes.add(file_hash)
                stats["new_indexed"] += 1

                if i % 50 == 0:
                    db.commit()
                    logger.info("[%d/%d] Indexed: %s", i, total_found, rel_path)

            except Exception:
                stats["errors"] += 1
                logger.error("Error processing %s", rel_path, exc_info=True)
                db.rollback()
                continue

        # Final commit
        db.commit()

    finally:
        db.close()

    elapsed = time.time() - t0
    logger.info(
        "Scan complete in %.1fs: %d found, %d new, %d skipped, %d errors",
        elapsed, stats["total_found"], stats["new_indexed"],
        stats["skipped_existing"], stats["errors"],
    )
    return stats


def _get_or_create_admin_user() -> str:
    """Get the admin user's ID, creating if necessary."""
    from app.core.security import hash_password

    db = get_sync_db()
    try:
        result = db.execute(select(User).where(User.role == "admin"))
        user = result.scalar_one_or_none()
        if user:
            user_id = str(user.id)
            db.close()
            return user_id

        # Create admin user
        user = User(
            username=settings.admin_username,
            email=settings.admin_email,
            password_hash=hash_password(settings.admin_password),
            role="admin",
        )
        db.add(user)
        db.commit()
        user_id = str(user.id)
        logger.info("Created admin user: %s (id=%s)", settings.admin_username, user_id)
        db.close()
        return user_id
    except Exception:
        db.rollback()
        db.close()
        raise


def main():
    """CLI entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    dry_run = "--dry" in sys.argv

    # Ensure tables exist
    Base.metadata.create_all(bind=sync_engine)

    user_id = _get_or_create_admin_user()
    stats = scan_library(user_id=user_id, dry_run=dry_run)
    print(f"\nScan results: {stats}")


if __name__ == "__main__":
    main()
