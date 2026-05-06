"""
Phase 2: People API endpoints.

GET  /api/v1/people                — list named people (face clusters)
GET  /api/v1/people/{id}/photos    — all photos featuring this person
POST /api/v1/people/{id}/name      — assign a name to a face cluster
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.face import Face
from app.models.person import Person
from app.models.photo import Photo
from app.models.user import User
from app.schemas.face import PersonBase, PersonDetail, PersonNameRequest, MergeIntoRequest
from app.schemas.photo import PhotoBase

router = APIRouter()


@router.get("", response_model=list[PersonBase])
async def list_people(
    sort: str = Query(default="face_count"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List all people (face clusters) for the current user."""
    # Normalise sort — strip any trailing modifiers (e.g. ":1") and fall back to default
    sort = sort.split(":")[0].strip()
    if sort not in {"face_count", "name", "created_at"}:
        sort = "face_count"
    # Exclude unnamed clusters with no faces — these are orphaned records
    # left when their faces were deleted (e.g. false-positive purge).
    query = select(Person).where(
        Person.user_id == user.id,
        Person.face_count > 0,
    )

    if sort == "name":
        query = query.order_by(Person.name.asc().nullslast(), Person.face_count.desc())
    elif sort == "created_at":
        query = query.order_by(Person.created_at.desc())
    else:
        query = query.order_by(Person.face_count.desc())

    result = await db.execute(query)
    return list(result.scalars().all())


@router.get("/{person_id}", response_model=PersonDetail)
async def get_person(
    person_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get a person with their face records."""
    person = await _get_person_or_404(db, person_id, user.id)

    # Eager-load faces separately to avoid lazy-load in async context
    faces_result = await db.execute(
        select(Face).where(Face.person_id == person_id).order_by(Face.created_at.desc())
    )
    faces = list(faces_result.scalars().all())

    return PersonDetail(
        id=person.id,
        name=person.name,
        face_count=person.face_count,
        created_at=person.created_at,
        updated_at=person.updated_at,
        faces=faces,
    )


@router.get("/{person_id}/photos", response_model=list[PhotoBase])
async def list_person_photos(
    person_id: uuid.UUID,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get all photos featuring this person."""
    await _get_person_or_404(db, person_id, user.id)

    offset = (page - 1) * limit
    query = (
        select(Photo)
        .join(Face, Face.photo_id == Photo.id)
        .where(Face.person_id == person_id, Photo.user_id == user.id)
        .order_by(Photo.taken_at.desc().nullslast())
        .distinct()
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(query)
    return list(result.scalars().all())


@router.post("/{person_id}/name", response_model=PersonBase)
async def name_person(
    person_id: uuid.UUID,
    body: PersonNameRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Assign or update a name for a person (face cluster)."""
    person = await _get_person_or_404(db, person_id, user.id)
    person.name = body.name
    return person


@router.post("/{person_id}/merge", response_model=PersonBase)
async def merge_people(
    person_id: uuid.UUID,
    body: MergeIntoRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Merge one or more person clusters into this person.

    All faces from the source clusters are reassigned to this person.
    Source person records are deleted. The target keeps its name if set;
    otherwise it inherits the name of the largest source.
    """
    target = await _get_person_or_404(db, person_id, user.id)

    for source_id in body.source_ids:
        if source_id == person_id:
            continue
        source = await _get_person_or_404(db, source_id, user.id)

        # Inherit name from source if target is unnamed and source is named
        if not target.name and source.name:
            target.name = source.name

        # Reassign all faces from source to target in one UPDATE
        await db.execute(
            update(Face)
            .where(Face.person_id == source_id)
            .values(person_id=person_id)
        )

        await db.delete(source)

    # Recount faces on the merged person
    count = await db.execute(
        select(func.count()).select_from(Face).where(Face.person_id == person_id)
    )
    target.face_count = count.scalar() or 0

    # Pick a new representative face (most recent)
    rep = await db.execute(
        select(Face.id)
        .where(Face.person_id == person_id)
        .order_by(Face.created_at.desc())
        .limit(1)
    )
    rep_id = rep.scalar_one_or_none()
    if rep_id:
        target.representative_face_id = rep_id

    await db.commit()
    await db.refresh(target)
    return target


# ── Helper ───────────────────────────────────────────────────

async def _get_person_or_404(db: AsyncSession, person_id: uuid.UUID, user_id: uuid.UUID) -> Person:
    result = await db.execute(
        select(Person).where(Person.id == person_id, Person.user_id == user_id)
    )
    person = result.scalar_one_or_none()
    if not person:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Person not found")
    return person
