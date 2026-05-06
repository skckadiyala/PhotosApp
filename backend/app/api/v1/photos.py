"""
Phase 1: Photo API endpoints.

GET /api/v1/photos?page=1&limit=50&sort=date_taken
GET /api/v1/photos/{photo_id}
GET /api/v1/photos/{photo_id}/thumbnail?size=medium
GET /api/v1/photos/{photo_id}/original
GET /api/v1/photos/metadata/{photo_id}
"""
import asyncio
import logging
import os
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel
from fastapi.responses import FileResponse, Response, StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, get_current_user_token_param
from app.config import get_settings
from app.core.database import get_db
from app.models.photo import Photo
from app.models.user import User
from app.schemas.photo import (
    PhotoBase,
    PhotoDetail,
    PhotoMetadataResponse,
    PaginatedPhotos,
    LibrarySummaryResponse,
    MonthPhotosResponse,
    PaginatedEventClusters,
    EventClusterPhotosResponse,
)
from app.utils.path import safe_resolve

router = APIRouter()
settings = get_settings()
logger = logging.getLogger(__name__)

VALID_THUMB_SIZES = {"small": "sm", "medium": "md", "large": "lg", "sm": "sm", "md": "md", "lg": "lg"}
VALID_SORT_FIELDS = {"date_taken", "created_at", "file_name", "file_size"}


@router.get("", response_model=PaginatedPhotos)
async def list_photos(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    sort: str = Query(default="date_taken"),
    media_type: str = Query(default=None, description="'video' to list only videos, 'image' for images only"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List photos with page/limit pagination, sorted by the given field descending."""
    base_filter = [Photo.user_id == user.id, Photo.is_hidden.is_(False)]

    # Filter by media type via mime_type prefix
    if media_type == "video":
        base_filter.append(Photo.mime_type.like("video/%"))
    elif media_type == "image":
        base_filter.append(Photo.mime_type.like("image/%"))

    query = select(Photo).where(*base_filter)

    # Sort
    if sort == "date_taken":
        query = query.order_by(Photo.taken_at.desc().nullslast(), Photo.created_at.desc())
    elif sort == "created_at":
        query = query.order_by(Photo.created_at.desc())
    elif sort == "file_name":
        query = query.order_by(Photo.file_name.asc())
    elif sort == "file_size":
        query = query.order_by(Photo.file_size.desc())
    else:
        query = query.order_by(Photo.taken_at.desc().nullslast(), Photo.created_at.desc())

    # Count total
    count_q = select(func.count()).select_from(Photo).where(*base_filter)
    total = (await db.execute(count_q)).scalar() or 0

    # Paginate
    offset = (page - 1) * limit
    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    items = list(result.scalars().all())

    total_pages = (total + limit - 1) // limit if total > 0 else 1

    return PaginatedPhotos(
        items=items,
        page=page,
        limit=limit,
        total=total,
        total_pages=total_pages,
    )


@router.get("/library-summary", response_model=LibrarySummaryResponse)
async def get_library_summary(
    media_type: str = Query(default="image", pattern="^(image|video)$"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return year/month groups with counts and cover photos in a single DB query.

    media_type: 'image' (default) or 'video'
    """
    import calendar
    from sqlalchemy import text

    mime_prefix = f"{media_type}/%"

    rows = (await db.execute(
        text("""
            WITH ranked AS (
                SELECT
                    id AS photo_id,
                    thumb_sm,
                    thumb_md,
                    EXTRACT(YEAR  FROM COALESCE(taken_at, created_at))::int AS yr,
                    EXTRACT(MONTH FROM COALESCE(taken_at, created_at))::int AS mo,
                    ROW_NUMBER() OVER (
                        PARTITION BY
                            EXTRACT(YEAR  FROM COALESCE(taken_at, created_at))::int,
                            EXTRACT(MONTH FROM COALESCE(taken_at, created_at))::int
                        ORDER BY COALESCE(taken_at, created_at) DESC NULLS LAST
                    ) AS rn,
                    COUNT(*) OVER (
                        PARTITION BY
                            EXTRACT(YEAR  FROM COALESCE(taken_at, created_at))::int,
                            EXTRACT(MONTH FROM COALESCE(taken_at, created_at))::int
                    ) AS cnt
                FROM photos
                WHERE user_id = :uid
                  AND is_hidden = false
                  AND mime_type LIKE :mime_prefix
            )
            SELECT yr, mo, cnt, photo_id, thumb_sm, thumb_md
            FROM   ranked
            WHERE  rn <= 4
            ORDER  BY yr DESC, mo DESC, rn ASC
        """),
        {"uid": str(user.id), "mime_prefix": mime_prefix},
    )).fetchall()

    # Build month -> year structure in Python
    months_dict: dict[tuple[int, int], dict] = {}
    for row in rows:
        yr, mo, cnt, photo_id = int(row.yr), int(row.mo), int(row.cnt), row.photo_id
        key = (yr, mo)
        if key not in months_dict:
            months_dict[key] = {
                "year": yr,
                "month": mo,
                "key": f"{yr}-{mo:02d}",
                "label": f"{calendar.month_name[mo]} {yr}",
                "count": cnt,
                "cover_photos": [],
            }
        months_dict[key]["cover_photos"].append({"id": photo_id, "thumb_sm": row.thumb_sm, "thumb_md": row.thumb_md})

    years_dict: dict[int, dict] = {}
    for (yr, mo), mdata in months_dict.items():
        if yr not in years_dict:
            years_dict[yr] = {"year": yr, "count": 0, "cover_photo": None, "months": []}
        years_dict[yr]["count"] += mdata["count"]
        years_dict[yr]["months"].append(mdata)
        if years_dict[yr]["cover_photo"] is None and mdata["cover_photos"]:
            years_dict[yr]["cover_photo"] = mdata["cover_photos"][0]

    years = sorted(years_dict.values(), key=lambda y: y["year"], reverse=True)
    for y in years:
        y["months"] = sorted(y["months"], key=lambda m: m["month"], reverse=True)

    return LibrarySummaryResponse(
        years=years,
        total=sum(y["count"] for y in years),
    )


@router.get("/by-month", response_model=MonthPhotosResponse)
async def list_photos_by_month(
    year: int = Query(..., ge=1900, le=2200),
    month: int = Query(..., ge=1, le=12),
    media_type: str = Query(default="image", pattern="^(image|video)$"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return all photos for a given calendar month.

    media_type: 'image' (default) or 'video'
    """
    date_expr = func.coalesce(Photo.taken_at, Photo.created_at)

    query = (
        select(Photo)
        .where(
            Photo.user_id == user.id,
            Photo.is_hidden.is_(False),
            Photo.mime_type.like(f"{media_type}/%"),
            func.extract("year", date_expr) == year,
            func.extract("month", date_expr) == month,
        )
        .order_by(date_expr.desc(), Photo.created_at.desc())
    )

    result = await db.execute(query)
    items = list(result.scalars().all())

    return MonthPhotosResponse(
        year=year,
        month=month,
        count=len(items),
        items=items,
    )


@router.get("/event-clusters", response_model=PaginatedEventClusters)
async def list_event_clusters(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    gap_hours: int = Query(default=6, ge=1, le=72),
    media_type: str = Query(default="image", pattern="^(image|video)$"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List adaptive event clusters (folder-like groups) for All Photos or All Videos.

    Reads from the pre-computed photo_clusters table when available (fast path).
    Falls back to the live 7-CTE query if the table hasn't been populated yet.

    Clustering rule: if gap between consecutive items is greater than
    ``gap_hours``, start a new cluster.
    media_type: 'image' (default) or 'video'
    """
    from sqlalchemy import text

    # ── Fast path: read from materialized photo_clusters table ────────────────
    # Count using the is_cover partial index — one cover row per cluster.
    materialized_count_row = (await db.execute(
        text("""
            SELECT COUNT(*)
            FROM photo_clusters
            WHERE user_id = :uid
              AND media_type = :media_type
              AND gap_hours = :gap_hours
              AND is_cover = true
        """),
        {"uid": str(user.id), "media_type": media_type, "gap_hours": gap_hours},
    )).scalar()

    if materialized_count_row and materialized_count_row > 0:
        total_clusters = int(materialized_count_row)
        total_pages = (total_clusters + limit - 1) // limit

        # JOIN photos for thumb_sm in one query (avoids N+1 correlated subquery).
        # cluster_id=0 is the newest event so ORDER BY cluster_id ASC = newest first.
        cluster_rows = (await db.execute(
            text("""
                SELECT
                    pc.cluster_id,
                    pc.cluster_start AS start_at,
                    pc.cluster_end AS end_at,
                    pc.cluster_count AS cnt,
                    pc.photo_id AS cover_photo_id,
                    ph.thumb_sm AS cover_thumb_sm,
                    ph.thumb_md AS cover_thumb_md
                FROM photo_clusters pc
                JOIN photos ph ON ph.id = pc.photo_id
                WHERE pc.user_id = :uid
                  AND pc.media_type = :media_type
                  AND pc.gap_hours = :gap_hours
                  AND pc.is_cover = true
                ORDER BY pc.cluster_id ASC
                LIMIT :limit OFFSET :offset
            """),
            {
                "uid": str(user.id),
                "media_type": media_type,
                "gap_hours": gap_hours,
                "limit": limit,
                "offset": (page - 1) * limit,
            },
        )).fetchall()

        items = [
            {
                "cluster_id": int(row.cluster_id),
                "start_at": row.start_at,
                "end_at": row.end_at,
                "count": int(row.cnt),
                "cover_photo": {"id": row.cover_photo_id, "thumb_sm": row.cover_thumb_sm, "thumb_md": row.cover_thumb_md}
                               if row.cover_photo_id else None,
            }
            for row in cluster_rows
        ]

        return PaginatedEventClusters(
            items=items,
            page=page,
            limit=limit,
            total=total_clusters,
            total_pages=total_pages,
        )

    # ── Slow fallback: live 7-CTE query (used until first cluster rebuild) ────
    gap_seconds = gap_hours * 3600
    offset = (page - 1) * limit
    mime_prefix = f"{media_type}/%"

    rows = (await db.execute(
        text("""
            WITH base AS (
                SELECT id, COALESCE(taken_at, created_at) AS ts
                FROM photos
                WHERE user_id = :uid
                  AND is_hidden = false
                  AND mime_type LIKE :mime_prefix
            ),
            ordered AS (
                SELECT id, ts,
                       LAG(ts) OVER (ORDER BY ts DESC, id) AS prev_ts
                FROM base
            ),
            flagged AS (
                SELECT id, ts,
                       CASE
                           WHEN prev_ts IS NULL THEN 1
                           WHEN EXTRACT(EPOCH FROM (prev_ts - ts)) > :gap_seconds THEN 1
                           ELSE 0
                       END AS is_new
                FROM ordered
            ),
            clustered AS (
                SELECT id, ts,
                       SUM(is_new) OVER (ORDER BY ts DESC, id ROWS UNBOUNDED PRECEDING) AS cluster_id
                FROM flagged
            ),
            ranked AS (
                SELECT cluster_id, id, ts,
                       ROW_NUMBER() OVER (PARTITION BY cluster_id ORDER BY ts DESC, id) AS rn
                FROM clustered
            ),
            agg AS (
                SELECT cluster_id,
                       MAX(ts) AS start_at,
                       MIN(ts) AS end_at,
                       COUNT(*) AS cnt
                FROM clustered
                GROUP BY cluster_id
            ),
            paged AS (
                SELECT *
                FROM agg
                ORDER BY start_at DESC
                OFFSET :offset
                LIMIT :limit
            )
            SELECT p.cluster_id,
                   p.start_at,
                   p.end_at,
                   p.cnt,
                   r.id AS cover_photo_id,
                   ph.thumb_sm AS cover_thumb_sm,
                   ph.thumb_md AS cover_thumb_md
            FROM paged p
            LEFT JOIN ranked r
              ON r.cluster_id = p.cluster_id
             AND r.rn = 1
            LEFT JOIN photos ph ON ph.id = r.id
            ORDER BY p.start_at DESC
        """),
        {
            "uid": str(user.id),
            "gap_seconds": gap_seconds,
            "offset": offset,
            "limit": limit,
            "mime_prefix": mime_prefix,
        },
    )).fetchall()

    total_clusters = (await db.execute(
        text("""
            WITH base AS (
                SELECT id, COALESCE(taken_at, created_at) AS ts
                FROM photos
                WHERE user_id = :uid
                  AND is_hidden = false
                  AND mime_type LIKE :mime_prefix
            ),
            ordered AS (
                SELECT id, ts,
                       LAG(ts) OVER (ORDER BY ts DESC, id) AS prev_ts
                FROM base
            ),
            flagged AS (
                SELECT id, ts,
                       CASE
                           WHEN prev_ts IS NULL THEN 1
                           WHEN EXTRACT(EPOCH FROM (prev_ts - ts)) > :gap_seconds THEN 1
                           ELSE 0
                       END AS is_new
                FROM ordered
            ),
            clustered AS (
                SELECT SUM(is_new) OVER (ORDER BY ts DESC, id ROWS UNBOUNDED PRECEDING) AS cluster_id
                FROM flagged
            )
            SELECT COALESCE(MAX(cluster_id), 0) AS total
            FROM clustered
        """),
        {
            "uid": str(user.id),
            "gap_seconds": gap_seconds,
            "mime_prefix": mime_prefix,
        },
    )).scalar() or 0

    total_pages = (total_clusters + limit - 1) // limit if total_clusters > 0 else 1

    items = [
        {
            "cluster_id": int(row.cluster_id),
            "start_at": row.start_at,
            "end_at": row.end_at,
            "count": int(row.cnt),
            "cover_photo": {"id": row.cover_photo_id, "thumb_sm": row.cover_thumb_sm, "thumb_md": row.cover_thumb_md} if row.cover_photo_id else None,
        }
        for row in rows
    ]

    return PaginatedEventClusters(
        items=items,
        page=page,
        limit=limit,
        total=total_clusters,
        total_pages=total_pages,
    )


@router.get("/event-clusters/{cluster_id}", response_model=EventClusterPhotosResponse)
async def get_event_cluster_photos(
    cluster_id: int,
    gap_hours: int = Query(default=6, ge=1, le=72),
    media_type: str = Query(default="image", pattern="^(image|video)$"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return all items inside one adaptive event cluster.

    Reads photo IDs from the pre-computed photo_clusters table when available,
    then fetches full Photo objects for those IDs.
    Falls back to the live CTE query when the table hasn't been populated yet.

    media_type: 'image' (default) or 'video'
    """
    from sqlalchemy import text

    # ── Fast path: read photo IDs from materialized table ─────────────────────
    mat_rows = (await db.execute(
        text("""
            SELECT pc.photo_id, pc.cluster_start, pc.cluster_end
            FROM photo_clusters pc
            WHERE pc.user_id = :uid
              AND pc.media_type = :media_type
              AND pc.gap_hours = :gap_hours
              AND pc.cluster_id = :cluster_id
            ORDER BY pc.cluster_start DESC NULLS LAST
        """),
        {
            "uid": str(user.id),
            "media_type": media_type,
            "gap_hours": gap_hours,
            "cluster_id": cluster_id,
        },
    )).fetchall()

    if mat_rows:
        photo_ids = [row.photo_id for row in mat_rows]
        photo_result = await db.execute(
            select(Photo).where(Photo.id.in_(photo_ids), Photo.user_id == user.id)
        )
        by_id = {str(p.id): p for p in photo_result.scalars().all()}
        items = [by_id[str(pid)] for pid in photo_ids if str(pid) in by_id]
        start_at = mat_rows[0].cluster_start
        end_at = mat_rows[-1].cluster_end

        return EventClusterPhotosResponse(
            cluster_id=cluster_id,
            gap_hours=gap_hours,
            start_at=start_at,
            end_at=end_at,
            count=len(items),
            items=items,
        )

    # ── Slow fallback: live CTE query ─────────────────────────────────────────
    gap_seconds = gap_hours * 3600
    mime_prefix = f"{media_type}/%"

    rows = (await db.execute(
        text("""
            WITH base AS (
                SELECT id, COALESCE(taken_at, created_at) AS ts
                FROM photos
                WHERE user_id = :uid
                  AND is_hidden = false
                  AND mime_type LIKE :mime_prefix
            ),
            ordered AS (
                SELECT id, ts,
                       LAG(ts) OVER (ORDER BY ts DESC, id) AS prev_ts
                FROM base
            ),
            flagged AS (
                SELECT id, ts,
                       CASE
                           WHEN prev_ts IS NULL THEN 1
                           WHEN EXTRACT(EPOCH FROM (prev_ts - ts)) > :gap_seconds THEN 1
                           ELSE 0
                       END AS is_new
                FROM ordered
            ),
            clustered AS (
                SELECT id, ts,
                       SUM(is_new) OVER (ORDER BY ts DESC, id ROWS UNBOUNDED PRECEDING) AS cluster_id
                FROM flagged
            )
            SELECT p.*, c.ts AS cluster_ts
            FROM photos p
            JOIN clustered c ON c.id = p.id
            WHERE c.cluster_id = :cluster_id
            ORDER BY c.ts DESC, p.created_at DESC
        """),
        {
            "uid": str(user.id),
            "gap_seconds": gap_seconds,
            "cluster_id": cluster_id,
            "mime_prefix": mime_prefix,
        },
    )).fetchall()

    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event cluster not found")

    photo_ids = [row.id for row in rows]
    photo_result = await db.execute(
        select(Photo).where(Photo.id.in_(photo_ids), Photo.user_id == user.id)
    )
    by_id = {str(p.id): p for p in photo_result.scalars().all()}
    items = [by_id[str(row.id)] for row in rows if str(row.id) in by_id]

    return EventClusterPhotosResponse(
        cluster_id=cluster_id,
        gap_hours=gap_hours,
        start_at=rows[0].cluster_ts,
        end_at=rows[-1].cluster_ts,
        count=len(items),
        items=items,
    )


class ArchiveRequest(BaseModel):
    photo_ids: list[str]


def _move_to_archive(src_path: str, photo_id_str: str) -> str:
    """Synchronous file move — runs in a thread to avoid blocking the event loop."""
    archive_dir = os.path.join(os.path.dirname(src_path), "._archive")
    os.makedirs(archive_dir, exist_ok=True)
    dst_name = os.path.basename(src_path)
    dst_path = os.path.join(archive_dir, dst_name)
    if os.path.exists(dst_path):
        base, ext = os.path.splitext(dst_name)
        dst_path = os.path.join(archive_dir, f"{base}_{photo_id_str[:8]}{ext}")
    os.rename(src_path, dst_path)
    return dst_path


@router.post("/archive")
async def archive_photos(
    body: ArchiveRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Move selected photos/videos to ._archive/ under their source directory and mark them hidden."""
    if not body.photo_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No photo IDs provided")

    # Validate UUIDs up front
    valid: list[tuple[str, uuid.UUID]] = []
    errors: list[dict] = []
    for photo_id_str in body.photo_ids:
        try:
            valid.append((photo_id_str, uuid.UUID(photo_id_str)))
        except ValueError:
            errors.append({"id": photo_id_str, "error": "Invalid UUID"})

    if not valid:
        return {"archived": [], "errors": errors}

    # Single query to fetch all photos at once
    valid_uuids = [uid for _, uid in valid]
    result = await db.execute(
        select(Photo).where(Photo.id.in_(valid_uuids), Photo.user_id == user.id)
    )
    photo_map = {str(p.id): p for p in result.scalars().all()}

    archived: list[str] = []

    for photo_id_str, _ in valid:
        photo = photo_map.get(photo_id_str)
        if not photo:
            errors.append({"id": photo_id_str, "error": "Not found"})
            continue

        src_path = safe_resolve(settings.photos_dir, photo.file_path)
        if not await asyncio.to_thread(os.path.isfile, src_path):
            errors.append({"id": photo_id_str, "error": "File not found on disk"})
            continue

        try:
            dst_path = await asyncio.to_thread(_move_to_archive, src_path, photo_id_str)
        except OSError as exc:
            errors.append({"id": photo_id_str, "error": str(exc)})
            continue

        photo.file_path = os.path.relpath(dst_path, settings.photos_dir)
        photo.is_hidden = True
        archived.append(photo_id_str)

    await db.commit()
    return {"archived": archived, "errors": errors}


@router.get("/metadata/{photo_id}", response_model=PhotoMetadataResponse)
async def get_photo_metadata(
    photo_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get detailed EXIF metadata for a photo."""
    photo = await _get_photo_or_404(db, photo_id, user.id)
    return photo


@router.get("/{photo_id}", response_model=PhotoDetail)
async def get_photo(
    photo_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get a single photo by ID."""
    result = await db.execute(
        select(Photo)
        .options(selectinload(Photo.location))
        .where(Photo.id == photo_id, Photo.user_id == user.id)
    )
    photo = result.scalar_one_or_none()
    if not photo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found")

    location_name = None
    if photo.location:
        parts = [p for p in [photo.location.city, photo.location.state, photo.location.country] if p]
        location_name = ", ".join(parts) if parts else photo.location.formatted

    detail = PhotoDetail.model_validate(photo)
    detail.location_name = location_name
    if settings.host_photos_dir:
        import os as _os
        detail.host_file_path = _os.path.join(settings.host_photos_dir, photo.file_path)
    return detail


_THUMB_FALLBACK: dict[str, list[str]] = {
    "sm": ["sm", "md", "lg"],
    "md": ["md", "lg", "sm"],
    "lg": ["lg", "md", "sm"],
}


@router.get("/{photo_id}/thumbnail")
async def serve_thumbnail(
    photo_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    size: str = Query(default="medium"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Serve a thumbnail image.
    size: small (200px), medium (800px), or large (1600px).

    Falls back to the next available size if the requested one is missing.
    Queues on-demand generation when no thumbnail exists yet.
    """
    size_key = VALID_THUMB_SIZES.get(size)
    if not size_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid size '{size}'. Use: small, medium, large",
        )

    photo = await _get_photo_or_404(db, photo_id, user.id)

    for try_size in _THUMB_FALLBACK[size_key]:
        thumb_rel = getattr(photo, f"thumb_{try_size}")
        if not thumb_rel:
            continue
        thumb_path = safe_resolve(settings.thumbnails_dir, thumb_rel)
        if os.path.isfile(thumb_path):
            return FileResponse(
                thumb_path,
                media_type="image/jpeg",
                headers={"Cache-Control": "public, max-age=31536000, immutable"},
            )

    # No thumbnail found — generate in background so it's ready on next request
    photo_id_str = str(photo.id)
    file_path = photo.file_path

    def _gen():
        from app.services.thumbnail import generate_thumbnails as _svc
        from app.core.database import get_sync_db
        from app.models.photo import Photo as PhotoModel
        from sqlalchemy import select as _select
        try:
            full_path = os.path.join(settings.photos_dir, file_path)
            thumbs = _svc(photo_id_str, full_path)
            db_sync = get_sync_db()
            try:
                p = db_sync.execute(_select(PhotoModel).where(PhotoModel.id == photo_id_str)).scalar_one_or_none()
                if p:
                    p.thumb_sm = thumbs.get("sm")
                    p.thumb_md = thumbs.get("md")
                    p.thumb_lg = thumbs.get("lg")
                    p.is_processed = True
                    db_sync.commit()
            finally:
                db_sync.close()
            logger.info("On-demand thumbnails generated for photo %s", photo_id_str)
        except Exception:
            logger.warning("On-demand thumbnail generation failed for photo %s", photo_id_str, exc_info=True)

    background_tasks.add_task(_gen)

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Thumbnail not available — generation queued",
    )


@router.get("/{photo_id}/original")
async def serve_original(
    photo_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Serve the full original photo via nginx X-Accel-Redirect.

    Auth is enforced here; nginx serves the file directly from disk so the
    Python worker is not blocked streaming bytes.
    """
    import urllib.parse
    photo = await _get_photo_or_404(db, photo_id, user.id)

    full_path = safe_resolve(settings.photos_dir, photo.file_path)
    if not os.path.isfile(full_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Original file not found on disk",
        )

    accel_path = "/protected-photos/" + urllib.parse.quote(photo.file_path, safe="/")
    return Response(
        status_code=200,
        headers={
            "X-Accel-Redirect": accel_path,
            "Content-Type": photo.mime_type,
            "Content-Disposition": f'inline; filename="{photo.file_name}"',
            "Cache-Control": "private, max-age=86400",
        },
    )


@router.get("/{photo_id}/stream")
async def stream_video(
    photo_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_token_param),
):
    """Serve a video via nginx X-Accel-Redirect (token auth for <video> tags).

    nginx handles byte-range requests natively so video seeking works without
    buffering the file through Python.
    """
    import urllib.parse
    photo = await _get_photo_or_404(db, photo_id, user.id)

    if not photo.mime_type.startswith("video/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Not a video file")

    full_path = safe_resolve(settings.photos_dir, photo.file_path)
    if not os.path.isfile(full_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video file not found on disk")

    accel_path = "/protected-photos/" + urllib.parse.quote(photo.file_path, safe="/")
    return Response(
        status_code=200,
        headers={
            "X-Accel-Redirect": accel_path,
            "Content-Type": photo.mime_type,
            "Content-Disposition": f'inline; filename="{photo.file_name}"',
            "Cache-Control": "private, max-age=86400",
        },
    )


@router.post("/{photo_id}/scan-faces")
async def scan_faces_for_photo(
    photo_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Re-run face detection on a single photo and recluster faces for the user."""
    photo = await _get_photo_or_404(db, photo_id, user.id)

    abs_path = os.path.join(settings.photos_dir, photo.file_path)
    if not os.path.isfile(abs_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Photo file not found on disk",
        )

    user_id_str = str(user.id)
    photo_id_str = str(photo_id)

    def _run():
        from app.core.database import get_sync_db
        from app.services.face_detector import detect_faces_in_photo
        from app.services.face_cluster import cluster_faces
        from app.models.face import Face as FaceModel
        from sqlalchemy import delete as sql_delete, select as sql_select

        def _iou(a, b):
            """Intersection-over-Union for two (top,right,bottom,left) boxes."""
            inter_top    = max(a["top"],    b["top"])
            inter_left   = max(a["left"],   b["left"])
            inter_bottom = min(a["bottom"], b["bottom"])
            inter_right  = min(a["right"],  b["right"])
            inter_w = max(0, inter_right  - inter_left)
            inter_h = max(0, inter_bottom - inter_top)
            inter   = inter_w * inter_h
            if inter == 0:
                return 0.0
            area_a = (a["right"] - a["left"]) * (a["bottom"] - a["top"])
            area_b = (b["right"] - b["left"]) * (b["bottom"] - b["top"])
            return inter / (area_a + area_b - inter)

        db_sync = get_sync_db()
        try:
            # Step 1: detect faces — abort early if detection itself raises
            new_faces = detect_faces_in_photo(abs_path)
            logger.info("scan-faces: detected %d face(s) in %s", len(new_faces), abs_path)

            # Step 2: load existing face records so we can preserve person assignments
            existing = db_sync.execute(
                sql_select(FaceModel).where(FaceModel.photo_id == photo_id_str)
            ).scalars().all()

            # Step 3: match each new detection to the closest existing face (by IoU)
            # Carry forward the person_id when IoU > 0.4 (same face, same spot)
            IOU_THRESHOLD = 0.4
            used_existing_ids: set = set()
            new_records = []
            for face_data in new_faces:
                loc = face_data["location"]
                best_iou, best_existing = 0.0, None
                for ex in existing:
                    ex_loc = {"top": ex.bbox_top, "right": ex.bbox_right,
                              "bottom": ex.bbox_bottom, "left": ex.bbox_left}
                    iou = _iou(loc, ex_loc)
                    if iou > best_iou:
                        best_iou, best_existing = iou, ex
                inherited_person_id = None
                if best_existing and best_iou >= IOU_THRESHOLD:
                    inherited_person_id = best_existing.person_id
                    used_existing_ids.add(best_existing.id)
                new_records.append((loc, face_data["embedding"], face_data.get("confidence", 1.0), inherited_person_id))

            # Step 4: delete ALL existing face records for this photo
            db_sync.execute(sql_delete(FaceModel).where(FaceModel.photo_id == photo_id_str))
            db_sync.commit()

            # Step 5: store newly detected faces (with inherited person_id where matched)
            for loc, embedding, confidence, person_id in new_records:
                db_sync.add(FaceModel(
                    photo_id=photo_id_str,
                    bbox_top=loc["top"],
                    bbox_right=loc["right"],
                    bbox_bottom=loc["bottom"],
                    bbox_left=loc["left"],
                    embedding=embedding.tolist(),
                    confidence=confidence,
                    person_id=str(person_id) if person_id else None,
                ))
            db_sync.commit()

            # Step 6: recluster all faces for this user
            cluster_faces(user_id_str)

        except Exception:
            db_sync.rollback()
            logger.error("scan-faces failed for photo %s", photo_id_str, exc_info=True)
        finally:
            db_sync.close()

    background_tasks.add_task(_run)
    return {"message": "Face scan started for this photo", "photo_id": photo_id_str, "status": "running"}


class ManualFaceRegion(BaseModel):
    """Bounding box in original image pixel coordinates (face_recognition order)."""
    top: int
    right: int
    bottom: int
    left: int


@router.post("/{photo_id}/faces/manual")
async def add_manual_face(
    photo_id: uuid.UUID,
    region: ManualFaceRegion,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Store an embedding for a user-drawn face bounding box on a single photo."""
    photo = await _get_photo_or_404(db, photo_id, user.id)

    abs_path = os.path.join(settings.photos_dir, photo.file_path)
    if not os.path.isfile(abs_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Photo file not found on disk",
        )

    # Basic sanity checks on the bounding box
    if region.top >= region.bottom or region.left >= region.right:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="Invalid bounding box: top must be < bottom and left must be < right")
    if (region.bottom - region.top) < 20 or (region.right - region.left) < 20:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="Selected region is too small (minimum 20x20 pixels)")

    user_id_str = str(user.id)
    photo_id_str = str(photo_id)
    loc = (region.top, region.right, region.bottom, region.left)

    def _run():
        import numpy as np
        from PIL import Image, ImageOps
        from deepface import DeepFace
        from app.core.database import get_sync_db
        from app.models.face import Face as FaceModel
        from app.services.face_cluster import cluster_faces

        db_sync = get_sync_db()
        try:
            pil = ImageOps.exif_transpose(Image.open(abs_path)).convert("RGB")
            img = np.array(pil)

            top, right, bottom, left = region.top, region.right, region.bottom, region.left

            # Crop the user-drawn region out of the image and compute embedding
            crop = img[top:bottom, left:right]
            if crop.size == 0:
                logger.warning("manual-face: empty crop for photo %s region %s", abs_path, loc)
                return

            results = DeepFace.represent(
                img_path=crop,
                model_name="ArcFace",
                detector_backend="skip",  # bbox is already known — skip re-detection
                enforce_detection=False,
                align=False,
            )
            if not results or not results[0].get("embedding"):
                logger.warning("manual-face: could not compute embedding for %s region %s", abs_path, loc)
                return

            embedding = results[0]["embedding"]

            db_sync.add(FaceModel(
                photo_id=photo_id_str,
                bbox_top=top,
                bbox_right=right,
                bbox_bottom=bottom,
                bbox_left=left,
                embedding=embedding,
                confidence=0.9,  # user-confirmed region
            ))
            db_sync.commit()
            logger.info("manual-face: stored face for photo %s at %s", photo_id_str, loc)

            cluster_faces(user_id_str)
        except Exception:
            db_sync.rollback()
            logger.error("manual-face: failed for photo %s", photo_id_str, exc_info=True)
        finally:
            db_sync.close()

    background_tasks.add_task(_run)
    return {"message": "Manual face region queued for processing", "photo_id": photo_id_str, "status": "running"}

async def _get_photo_or_404(db: AsyncSession, photo_id: uuid.UUID, user_id: uuid.UUID) -> Photo:
    result = await db.execute(
        select(Photo).where(Photo.id == photo_id, Photo.user_id == user_id)
    )
    photo = result.scalar_one_or_none()
    if not photo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found")
    return photo
