"""
Backfill taken_at for photos that have no EXIF date by using the file's
modification time (mtime). Runs entirely inside the backend container.

Usage:
    docker exec photosapp-backend-1 python /app/scripts/backfill_taken_at.py

Safe to re-run — only touches rows where taken_at IS NULL and the file exists.
"""
import logging
import os
import sys
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger(__name__)

sys.path.insert(0, "/app")

from sqlalchemy import select, update
from app.core.database import get_sync_db
from app.models.photo import Photo
from app.config import get_settings

settings = get_settings()


def main():
    db = get_sync_db()
    try:
        rows = db.execute(
            select(Photo.id, Photo.file_path).where(Photo.taken_at.is_(None))
        ).fetchall()

        log.info("Found %d photos with taken_at IS NULL", len(rows))

        updated = 0
        missing = 0
        BATCH = 500

        for i, (photo_id, file_path) in enumerate(rows, 1):
            abs_path = os.path.join(settings.photos_dir, file_path)
            try:
                mtime = os.path.getmtime(abs_path)
                taken_at = datetime.utcfromtimestamp(mtime)
                db.execute(
                    update(Photo).where(Photo.id == photo_id).values(taken_at=taken_at)
                )
                updated += 1
            except OSError:
                missing += 1

            if i % BATCH == 0:
                db.commit()
                log.info("[%d/%d] Updated %d, missing %d", i, len(rows), updated, missing)

        db.commit()
        log.info("Done — updated %d photos, %d files missing on disk", updated, missing)
    finally:
        db.close()


if __name__ == "__main__":
    main()
