"""Celery tasks for reverse-geocoding photos.

Nominatim enforces a strict 1 req/s rate limit. Rather than blocking with
time.sleep(), we dispatch one task per new coordinate and space them using
Celery's countdown parameter. Photos whose coordinates are already cached in
the locations table are updated in a single batch DB write (no API call).
"""
import logging
import uuid as _uuid

from sqlalchemy import select

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="geocode_photo", bind=True, max_retries=3)
def geocode_photo(self, photo_id: str):
    """Reverse-geocode one photo and persist its location_id."""
    from app.core.database import get_sync_db
    from app.models.photo import Photo
    from app.services.geocoder import _get_or_create_location

    db = get_sync_db()
    try:
        photo = db.execute(
            select(Photo).where(Photo.id == _uuid.UUID(photo_id))
        ).scalar_one_or_none()

        if not photo or not photo.gps_latitude or photo.location_id:
            return

        loc = _get_or_create_location(db, photo.gps_latitude, photo.gps_longitude)
        photo.location_id = loc.id
        db.commit()
        logger.info("Geocoded photo %s → %s", photo_id, loc.formatted)
    except Exception as exc:
        db.rollback()
        raise self.retry(exc=exc, countdown=60)
    finally:
        db.close()


def dispatch_geocode_batch(user_id: str, max_batch: int = 200) -> dict:
    """Enqueue geocoding tasks for photos that have GPS but no location_id.

    Photos with coordinates already in the locations table get their
    location_id set in one batch write (no Nominatim call, returns immediately).
    Photos that need a new Nominatim lookup are dispatched as individual tasks
    with countdown spacing of 1.2s to honour the 1 req/s rate limit.

    Never blocks — safe to call from the server startup thread.
    """
    from app.core.database import get_sync_db
    from app.models.photo import Photo
    from app.models.location import Location

    uid = _uuid.UUID(user_id) if isinstance(user_id, str) else user_id
    db = get_sync_db()
    try:
        photos = db.execute(
            select(Photo)
            .where(
                Photo.user_id == uid,
                Photo.gps_latitude.isnot(None),
                Photo.gps_longitude.isnot(None),
                Photo.location_id.is_(None),
            )
            .limit(max_batch)
        ).scalars().all()

        if not photos:
            return {"immediate": 0, "queued": 0}

        immediate = 0
        nominatim_idx = 0

        for photo in photos:
            lat_r = round(photo.gps_latitude, 3)
            lng_r = round(photo.gps_longitude, 3)

            existing = db.execute(
                select(Location).where(
                    Location.latitude == lat_r,
                    Location.longitude == lng_r,
                )
            ).scalar_one_or_none()

            if existing:
                photo.location_id = existing.id
                immediate += 1
            else:
                # Space tasks 1.2s apart so each Nominatim call is isolated.
                geocode_photo.apply_async(
                    args=[str(photo.id)],
                    countdown=nominatim_idx * 1.2,
                )
                nominatim_idx += 1

        db.commit()
        stats = {"immediate": immediate, "queued": nominatim_idx}
        logger.info("Geocode batch dispatched: %s", stats)
        return stats
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
