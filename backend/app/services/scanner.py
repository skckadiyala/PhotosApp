"""
Recursive photo scanner.

Walks PHOTOS_DIR, discovers image files, and for each new file:
  1. Computes SHA-256 hash (dedup)
  2. Extracts EXIF metadata (lightweight — no image decode)
  3. Inserts a Photo row into PostgreSQL
  4. Dispatches the full processing pipeline to Celery workers
     (thumbnails, metadata, face detection, tagging run out-of-process)

Keeping thumbnail generation and face detection OUT of the scanner means
the backend process stays lightweight regardless of library size.
"""
import gc
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

logger = logging.getLogger(__name__)
settings = get_settings()

# Commit and dispatch Celery tasks in batches to keep the SQLAlchemy session
# small and let workers start processing while the scan is still running.
_BATCH_SIZE = 50


def compute_file_hash(path: str, chunk_size: int = 65536) -> str:
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(chunk_size):
            sha256.update(chunk)
    return sha256.hexdigest()


def discover_files(root: str):
    """Yield absolute paths of all supported files under root (generator)."""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for fname in filenames:
            if fname.startswith("."):
                continue
            if os.path.splitext(fname)[1].lower() in settings.supported_extensions:
                yield os.path.join(dirpath, fname)


def scan_library(user_id: str, dry_run: bool = False) -> dict:
    """
    Scan the photos directory and index new files into the database.

    New files get a lightweight DB record inserted immediately, then the
    full processing pipeline (thumbnails, EXIF, faces, tags) is dispatched
    to Celery workers.  The backend process never loads image pixel data.

    Returns:
        Stats dict: {total_found, new_indexed, skipped_existing, errors}
    """
    photos_dir = settings.photos_dir
    if not os.path.isdir(photos_dir):
        logger.error("Photos directory does not exist: %s", photos_dir)
        return {"error": f"Directory not found: {photos_dir}"}

    logger.info("Scanning %s for photos...", photos_dir)
    t0 = time.time()

    if dry_run:
        count = 0
        for path in discover_files(photos_dir):
            print(os.path.relpath(path, photos_dir))
            count += 1
        return {"total_found": count, "dry_run": True}

    stats = {"total_found": 0, "new_indexed": 0, "skipped_existing": 0, "errors": 0}
    db = get_sync_db()

    try:
        # Load existing paths and hashes into plain Python sets so we can do
        # O(1) lookups without touching the SQLAlchemy identity map.
        existing_paths: set[str] = set()
        existing_hashes: set[str] = set()
        for row in db.execute(select(Photo.file_path, Photo.file_hash).where(Photo.user_id == user_id)):
            existing_paths.add(row[0])
            if row[1]:
                existing_hashes.add(row[1])
        logger.info("Found %d existing photos in database", len(existing_paths))

        # Batch of (photo_id, rel_path) pairs accumulated between commits.
        # Tasks are dispatched only after the DB row is committed so workers
        # can safely read the photo record.
        pending_dispatch: list[tuple[str, str]] = []

        for abs_path in discover_files(photos_dir):
            stats["total_found"] += 1
            i = stats["total_found"]
            rel_path = os.path.relpath(abs_path, photos_dir)

            try:
                if rel_path in existing_paths:
                    stats["skipped_existing"] += 1
                    continue

                file_hash = compute_file_hash(abs_path)

                if file_hash in existing_hashes:
                    stats["skipped_existing"] += 1
                    if i % 100 == 0:
                        logger.info("[%d] Skipping (moved/renamed): %s", i, rel_path)
                    continue

                meta = extract_metadata(abs_path)

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
                db.flush()

                pending_dispatch.append((str(photo.id), rel_path))
                existing_hashes.add(file_hash)
                stats["new_indexed"] += 1

                if stats["new_indexed"] % _BATCH_SIZE == 0:
                    db.commit()
                    # Clear the identity map so processed Photo objects can be GC'd.
                    db.expunge_all()
                    _dispatch_batch(pending_dispatch)
                    pending_dispatch.clear()
                    gc.collect()
                    logger.info("[%d found] Indexed %d new photos so far", i, stats["new_indexed"])

            except Exception:
                stats["errors"] += 1
                logger.error("Error processing %s", rel_path, exc_info=True)
                db.rollback()
                pending_dispatch.clear()

        # Final commit + dispatch for the last partial batch
        db.commit()
        db.expunge_all()
        _dispatch_batch(pending_dispatch)

    finally:
        db.close()

    elapsed = time.time() - t0
    logger.info(
        "Scan complete in %.1fs: %d found, %d new, %d skipped, %d errors",
        elapsed, stats["total_found"], stats["new_indexed"],
        stats["skipped_existing"], stats["errors"],
    )
    return stats


def _dispatch_batch(pairs: list[tuple[str, str]]) -> None:
    """Dispatch the Celery processing pipeline for a list of (photo_id, rel_path) pairs."""
    if not pairs:
        return
    try:
        from app.workers.pipeline import dispatch_photo_pipeline
        for photo_id, rel_path in pairs:
            dispatch_photo_pipeline(photo_id, rel_path)
    except Exception:
        logger.warning("Failed to dispatch pipeline tasks for batch", exc_info=True)


def _get_or_create_admin_user() -> str:
    """Return the admin user's ID, creating the account if it doesn't exist."""
    from app.core.security import hash_password

    db = get_sync_db()
    try:
        result = db.execute(select(User).where(User.role == "admin"))
        user = result.scalar_one_or_none()
        if user:
            return str(user.id)

        user = User(
            username=settings.admin_username,
            email=settings.admin_email,
            password_hash=hash_password(settings.admin_password),
            role="admin",
        )
        db.add(user)
        db.commit()
        logger.info("Created admin user: %s (id=%s)", settings.admin_username, user.id)
        return str(user.id)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main():
    """CLI entry point."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    dry_run = "--dry" in sys.argv
    Base.metadata.create_all(bind=sync_engine)
    user_id = _get_or_create_admin_user()
    stats = scan_library(user_id=user_id, dry_run=dry_run)
    print(f"\nScan results: {stats}")


if __name__ == "__main__":
    main()
