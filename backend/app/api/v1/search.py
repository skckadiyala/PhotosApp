from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.face import Face
from app.models.location import Location
from app.models.person import Person
from app.models.photo import Photo
from app.models.tag import PhotoTag, Tag
from app.models.user import User

router = APIRouter()


@router.get("")
async def search_photos(
    q: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    location: str | None = None,
    person_id: str | None = None,
    tag: str | None = None,
    camera: str | None = None,
    cursor: str | None = None,
    limit: int = Query(default=50, le=200),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(Photo).where(Photo.user_id == user.id, Photo.is_hidden.is_(False))

    if q:
        pattern = f"%{q}%"
        query = query.where(
            or_(
                Photo.file_name.ilike(pattern),
                Photo.camera_model.ilike(pattern),
            )
        )

    if from_date:
        query = query.where(Photo.taken_at >= from_date)
    if to_date:
        query = query.where(Photo.taken_at <= to_date)

    if location:
        query = query.join(Location, Photo.location_id == Location.id).where(
            or_(
                Location.city.ilike(f"%{location}%"),
                Location.country.ilike(f"%{location}%"),
                Location.state.ilike(f"%{location}%"),
            )
        )

    if person_id:
        query = query.join(Face, Face.photo_id == Photo.id).where(Face.person_id == person_id)

    if tag:
        query = (
            query.join(PhotoTag, PhotoTag.photo_id == Photo.id)
            .join(Tag, PhotoTag.tag_id == Tag.id)
            .where(Tag.name.ilike(f"%{tag}%"))
        )

    if camera:
        query = query.where(Photo.camera_model.ilike(f"%{camera}%"))

    query = query.order_by(Photo.taken_at.desc().nullslast()).limit(limit)
    result = await db.execute(query)
    return {"items": result.scalars().all()}


@router.get("/suggestions")
async def search_suggestions(
    q: str = Query(min_length=1),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    suggestions = []
    pattern = f"{q}%"

    # Tags
    tags_result = await db.execute(select(Tag.name).where(Tag.name.ilike(pattern)).limit(5))
    suggestions.extend([f"tag:{name}" for name in tags_result.scalars().all()])

    # People
    people_result = await db.execute(
        select(Person.name).where(Person.name.ilike(pattern)).limit(5)
    )
    suggestions.extend([f"person:{name}" for name in people_result.scalars().all()])

    # Locations
    locations_result = await db.execute(
        select(Location.city).where(Location.city.ilike(pattern)).distinct().limit(5)
    )
    suggestions.extend([f"location:{city}" for city in locations_result.scalars().all()])

    return {"suggestions": suggestions}
