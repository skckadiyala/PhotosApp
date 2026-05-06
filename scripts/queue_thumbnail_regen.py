"""
Reset all thumbnail paths in the DB and re-queue Celery thumbnail generation
for every photo in the library.

Run this AFTER switching to the Docker-internal thumbnails_cache volume so that
the worker writes fresh WebP thumbnails to the SSD-backed volume.

Usage (run from inside the backend container):
    docker compose exec backend python /app/scripts/queue_thumbnail_regen.py

Progress is logged to stdout. Safe to interrupt and re-run — photos whose
thumbnail files already exist on disk are skipped by the worker.
"""
import logging
import os
import sys
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger(__name__)

# Add /app to path so app imports work inside the container
sys.path.insert(0, "/app")

from sqlalchemy import select, update
from app.core.database import get_sync_db
from app.models.photo import Photo
from app.workers.celery_app import celery_app  # noqa: F401 — needed to set up task registry
from app.config import get_settings

settings = get_settings()


def main():
    db = get_sync_db()
    try:
        photos = db.execute(select(Photo)).scalars().all()
        total = len(photos)
        log.info("Found %d photos — clearing thumbnail paths and queuing regeneration", total)

        # Clear all thumbnail paths in one UPDATE so the backend immediately
        # stops serving stale paths pointing to the old external-HDD volume.
        db.execute(
            update(Photo).values(thumb_sm=None, thumb_md=None, thumb_lg=None, is_processed=False)
        )
        db.commit()
        log.info("Cleared thumbnail paths for all %d photos", total)

        # Re-queue a generate_thumbnails Celery task for each photo.
        # Dispatch in small bursts to avoid flooding Redis.
        BURST = 200
        queued = 0
        for i, photo in enumerate(photos, 1):
            abs_path = os.path.join(settings.photos_dir, photo.file_path)
            celery_app.send_task(
                "generate_thumbnails",
                args=[str(photo.id), photo.file_path],
                queue="thumbnails",
            )
            queued += 1
            if i % BURST == 0:
                log.info("[%d/%d] Queued %d tasks so far…", i, total, queued)
                time.sleep(0.1)  # brief pause to avoid Redis write spike

        log.info("Done — %d thumbnail tasks queued. Worker will process overnight.", queued)
    finally:
        db.close()


if __name__ == "__main__":
    main()
