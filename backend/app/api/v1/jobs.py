import logging
import os

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.config import get_settings
from app.core.database import get_db
from app.models.photo import Photo
from app.models.user import User
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/status")
async def get_job_status(user: User = Depends(get_current_user)):
    """Get overview of background processing queues."""
    inspect = celery_app.control.inspect()
    active = inspect.active() or {}
    reserved = inspect.reserved() or {}

    total_active = sum(len(tasks) for tasks in active.values())
    total_reserved = sum(len(tasks) for tasks in reserved.values())

    return {
        "active": total_active,
        "queued": total_reserved,
        "workers": list(active.keys()),
    }


@router.post("/regenerate-thumbnails")
async def regenerate_thumbnails(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Queue thumbnail regeneration via Celery for all photos with any missing size.

    Tasks are processed by the celery_worker container so the API stays responsive.
    """
    settings = get_settings()

    result = await db.execute(
        select(Photo.id, Photo.file_path, Photo.thumb_sm, Photo.thumb_md, Photo.thumb_lg)
        .where(Photo.user_id == user.id, Photo.is_hidden.is_(False))
    )
    rows = result.all()

    def _needs_regen(row) -> bool:
        for attr in (row.thumb_sm, row.thumb_md, row.thumb_lg):
            if not attr:
                return True
            if not os.path.isfile(os.path.join(settings.thumbnails_dir, attr)):
                return True
        return False

    from app.workers.tasks.thumbnail import generate_thumbnails as _thumb_task

    queued = 0
    for row in rows:
        if _needs_regen(row):
            _thumb_task.apply_async(
                args=[str(row.id), row.file_path],
                queue="thumbnails",
            )
            queued += 1

    logger.info("Queued %d thumbnail tasks via Celery (user %s)", queued, user.id)
    return {"queued": queued, "total_checked": len(rows)}


@router.get("/{job_id}")
async def get_job_detail(job_id: str, user: User = Depends(get_current_user)):
    """Get status of a specific Celery task."""
    result = celery_app.AsyncResult(job_id)
    return {
        "job_id": job_id,
        "status": result.status,
        "result": result.result if result.ready() else None,
    }
