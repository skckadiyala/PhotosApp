"""Orchestrates the processing pipeline for a newly discovered photo."""
import logging

from celery import chain

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def dispatch_photo_pipeline(photo_id: str, file_path: str):
    """
    Dispatch the full processing pipeline for a photo:
    1. Generate thumbnails (fast, high priority)
    2. Extract EXIF metadata
    3. Detect faces + extract embeddings
    4. AI auto-tagging

    Thumbnails run first so the photo appears in the UI quickly.
    The rest run in parallel after thumbnails complete.
    """
    from app.workers.tasks.thumbnail import generate_thumbnails
    from app.workers.tasks.metadata import extract_metadata
    from app.workers.tasks.faces import detect_faces
    from app.workers.tasks.tagging import auto_tag_photo

    # Thumbnails first, then the rest in parallel via group
    from celery import group

    pipeline = chain(
        generate_thumbnails.s(photo_id, file_path),
        group(
            extract_metadata.si(photo_id, file_path),
            detect_faces.si(photo_id, file_path),
            auto_tag_photo.si(photo_id, file_path),
        ),
    )

    result = pipeline.apply_async()
    logger.info("Dispatched processing pipeline for photo %s: %s", photo_id, result.id)
    return result.id
