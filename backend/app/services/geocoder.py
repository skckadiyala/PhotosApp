"""Reverse geocoding service using geopy + Nominatim.

Converts GPS coordinates to human-readable location strings and stores
them in the locations table. Includes coordinate rounding to deduplicate
nearby locations and rate limiting for Nominatim's usage policy.
"""
import logging
import time
import uuid

from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.location import Location
from app.models.photo import Photo
from app.core.database import get_sync_db

logger = logging.getLogger(__name__)

# Round to ~111m precision to deduplicate nearby coords
COORD_PRECISION = 3  # decimal places


def _round_coord(val: float) -> float:
    return round(val, COORD_PRECISION)


def _find_existing_location(db: Session, lat: float, lng: float) -> Location | None:
    """Find an existing Location record matching rounded coordinates."""
    return db.execute(
        select(Location).where(
            Location.latitude == lat,
            Location.longitude == lng,
        )
    ).scalar_one_or_none()


def _reverse_geocode(lat: float, lng: float) -> dict:
    """Call Nominatim reverse geocoder. Returns address components."""
    import ssl
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    geolocator = Nominatim(user_agent="photosapp-selfhosted/1.0", timeout=10, ssl_context=ctx)
    try:
        location = geolocator.reverse(f"{lat}, {lng}", language="en", exactly_one=True)
        if location and location.raw.get("address"):
            addr = location.raw["address"]
            city = (
                addr.get("city")
                or addr.get("town")
                or addr.get("village")
                or addr.get("municipality")
                or addr.get("hamlet")
            )
            state = addr.get("state") or addr.get("region") or addr.get("province")
            country = addr.get("country")
            formatted = location.address
            return {
                "city": city,
                "state": state,
                "country": country,
                "formatted": formatted,
            }
    except (GeocoderTimedOut, GeocoderServiceError) as e:
        logger.warning("Geocoding failed for (%s, %s): %s", lat, lng, e)
    except Exception:
        logger.warning("Geocoding failed for (%s, %s)", lat, lng, exc_info=True)
    return {"city": None, "state": None, "country": None, "formatted": None}


def _get_or_create_location(db: Session, lat: float, lng: float) -> Location:
    """Get existing location or create a new one via reverse geocoding."""
    rounded_lat = _round_coord(lat)
    rounded_lng = _round_coord(lng)

    existing = _find_existing_location(db, rounded_lat, rounded_lng)
    if existing:
        return existing

    # Reverse geocode and create new location
    geo = _reverse_geocode(lat, lng)
    loc = Location(
        id=uuid.uuid4(),
        latitude=rounded_lat,
        longitude=rounded_lng,
        city=geo["city"],
        state=geo["state"],
        country=geo["country"],
        formatted=geo["formatted"],
    )
    db.add(loc)
    db.flush()
    logger.info("Created location: %s (%s, %s)", geo.get("formatted", "?"), rounded_lat, rounded_lng)

    # Nominatim rate limit: max 1 request/second
    time.sleep(1.1)
    return loc


def geocode_all_photos(user_id: str | None = None) -> dict:
    """Reverse-geocode all photos that have GPS but no location_id."""
    db = get_sync_db()
    try:
        query = (
            select(Photo)
            .where(
                Photo.gps_latitude.isnot(None),
                Photo.gps_longitude.isnot(None),
                Photo.location_id.is_(None),
            )
        )
        if user_id:
            query = query.where(Photo.user_id == uuid.UUID(user_id) if isinstance(user_id, str) else Photo.user_id == user_id)

        photos = db.execute(query).scalars().all()
        logger.info("Geocoding %d photos with GPS but no location...", len(photos))

        geocoded = 0
        errors = 0
        for photo in photos:
            try:
                loc = _get_or_create_location(db, photo.gps_latitude, photo.gps_longitude)
                photo.location_id = loc.id
                geocoded += 1
            except Exception:
                logger.warning("Failed to geocode photo %s", photo.id, exc_info=True)
                errors += 1

        db.commit()
        stats = {"total": len(photos), "geocoded": geocoded, "errors": errors}
        logger.info("Geocoding complete: %s", stats)
        return stats
    except Exception:
        db.rollback()
        logger.error("Geocoding batch failed", exc_info=True)
        raise
    finally:
        db.close()
