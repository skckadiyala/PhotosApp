import math

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import Numeric, Text, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.location import Location
from app.models.photo import Photo
from app.models.user import User

router = APIRouter()


# ── Schemas ──────────────────────────────────────────────────

class MapCluster(BaseModel):
    lat: float
    lng: float
    count: int
    preview_photo_id: str
    location_label: str | None = None


class MapClustersResponse(BaseModel):
    clusters: list[MapCluster]


class MapPhotoItem(BaseModel):
    id: str
    file_name: str
    thumb_sm: str | None = None
    lat: float
    lng: float
    location_label: str | None = None

    model_config = {"from_attributes": True}


class MapPhotosResponse(BaseModel):
    items: list[MapPhotoItem]


class LocationItem(BaseModel):
    id: str
    city: str | None = None
    state: str | None = None
    country: str | None = None
    formatted: str | None = None
    latitude: float
    longitude: float
    photo_count: int


class LocationsResponse(BaseModel):
    items: list[LocationItem]


# ── Endpoints ────────────────────────────────────────────────

@router.get("/clusters", response_model=MapClustersResponse)
async def get_map_clusters(
    zoom: int = Query(default=5, ge=1, le=20),
    sw_lat: float = Query(default=-90),
    sw_lng: float = Query(default=-180),
    ne_lat: float = Query(default=90),
    ne_lng: float = Query(default=180),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get clustered photo markers for the visible map area."""
    precision = max(1, min(6, zoom - 2))

    lat_bucket = func.round(func.cast(Photo.gps_latitude, Numeric), precision)
    lng_bucket = func.round(func.cast(Photo.gps_longitude, Numeric), precision)

    query = (
        select(
            lat_bucket.label("lat"),
            lng_bucket.label("lng"),
            func.count(Photo.id).label("count"),
            func.min(func.cast(Photo.id, Text)).label("preview_photo_id"),
        )
        .where(
            Photo.user_id == user.id,
            Photo.gps_latitude.isnot(None),
            Photo.gps_longitude.isnot(None),
            Photo.gps_latitude.between(sw_lat, ne_lat),
            Photo.gps_longitude.between(sw_lng, ne_lng),
        )
        .group_by(lat_bucket, lng_bucket)
        .order_by(func.count(Photo.id).desc())
        .limit(200)
    )

    result = await db.execute(query)
    clusters = []
    for row in result.all():
        # Find location label for this cluster
        loc_query = (
            select(Location.city, Location.country)
            .join(Photo, Photo.location_id == Location.id)
            .where(Photo.user_id == user.id, Photo.location_id.isnot(None))
            .limit(1)
        )
        loc_result = await db.execute(loc_query)
        loc_row = loc_result.first()
        label = None
        if loc_row and loc_row.city:
            label = f"{loc_row.city}, {loc_row.country}" if loc_row.country else loc_row.city

        clusters.append(MapCluster(
            lat=float(row.lat),
            lng=float(row.lng),
            count=row.count,
            preview_photo_id=str(row.preview_photo_id),
            location_label=label,
        ))

    return MapClustersResponse(clusters=clusters)


@router.get("/photos", response_model=MapPhotosResponse)
async def get_photos_at_location(
    lat: float = Query(...),
    lng: float = Query(...),
    radius: float = Query(default=50, description="Radius in km"),
    limit: int = Query(default=50, le=200),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get photos near a specific coordinate."""
    # 1 degree latitude ≈ 111km
    lat_range = radius / 111.0
    lng_range = radius / (111.0 * max(0.01, abs(math.cos(math.radians(lat)))))

    query = (
        select(Photo)
        .outerjoin(Location, Photo.location_id == Location.id)
        .where(
            Photo.user_id == user.id,
            Photo.gps_latitude.isnot(None),
            Photo.gps_longitude.isnot(None),
            Photo.gps_latitude.between(lat - lat_range, lat + lat_range),
            Photo.gps_longitude.between(lng - lng_range, lng + lng_range),
        )
        .order_by(Photo.taken_at.desc().nullslast())
        .limit(limit)
    )
    result = await db.execute(query)
    photos = result.scalars().all()

    items = []
    for p in photos:
        items.append(MapPhotoItem(
            id=str(p.id),
            file_name=p.file_name,
            thumb_sm=p.thumb_sm,
            lat=p.gps_latitude,
            lng=p.gps_longitude,
            location_label=None,
        ))
    return MapPhotosResponse(items=items)


@router.get("/locations", response_model=LocationsResponse)
async def get_locations(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get all unique locations with photo counts."""
    query = (
        select(
            Location.id,
            Location.city,
            Location.state,
            Location.country,
            Location.formatted,
            Location.latitude,
            Location.longitude,
            func.count(Photo.id).label("photo_count"),
        )
        .join(Photo, Photo.location_id == Location.id)
        .where(Photo.user_id == user.id)
        .group_by(Location.id)
        .order_by(func.count(Photo.id).desc())
    )
    result = await db.execute(query)
    items = [
        LocationItem(
            id=str(row.id),
            city=row.city,
            state=row.state,
            country=row.country,
            formatted=row.formatted,
            latitude=row.latitude,
            longitude=row.longitude,
            photo_count=row.photo_count,
        )
        for row in result.all()
    ]
    return LocationsResponse(items=items)
