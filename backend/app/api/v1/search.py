import re
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, extract, func, or_, select
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
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=100, le=500),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(Photo).where(Photo.user_id == user.id, Photo.is_hidden.is_(False))

    if q:
        q_stripped = q.strip()

        # If q looks like a bare year (e.g. "2025") → filter by year
        if re.fullmatch(r'(19|20)\d{2}', q_stripped):
            query = query.where(extract('year', Photo.taken_at) == int(q_stripped))
        else:
            # If q looks like "Month YYYY" or "Mon YYYY" (e.g. "January 2025", "Jan 2025")
            dt_match = None
            for fmt in ('%B %Y', '%b %Y'):
                try:
                    dt_match = datetime.strptime(q_stripped, fmt)
                    break
                except ValueError:
                    pass

            if dt_match is not None:
                query = query.where(
                    and_(
                        extract('year', Photo.taken_at) == dt_match.year,
                        extract('month', Photo.taken_at) == dt_match.month,
                    )
                )
            else:
                # Full text search: filename, camera, person name, location
                pattern = f"%{q}%"
                person_photo_ids = (
                    select(Face.photo_id)
                    .join(Person, Person.id == Face.person_id)
                    .where(Person.name.ilike(pattern))
                    .scalar_subquery()
                )
                location_photo_ids = (
                    select(Photo.id)
                    .join(Location, Photo.location_id == Location.id)
                    .where(
                        or_(
                            Location.city.ilike(pattern),
                            Location.country.ilike(pattern),
                            Location.state.ilike(pattern),
                            Location.formatted.ilike(pattern),
                        )
                    )
                    .scalar_subquery()
                )
                query = query.where(
                    or_(
                        Photo.file_name.ilike(pattern),
                        Photo.camera_model.ilike(pattern),
                        Photo.id.in_(person_photo_ids),
                        Photo.id.in_(location_photo_ids),
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
                Location.formatted.ilike(f"%{location}%"),
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

    query = query.order_by(Photo.taken_at.desc().nullslast())

    # Count total matching rows before pagination
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    offset = (page - 1) * limit
    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    items = list(result.scalars().all())
    total_pages = (total + limit - 1) // limit if total > 0 else 1

    return {"items": items, "page": page, "limit": limit, "total": total, "total_pages": total_pages}


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
