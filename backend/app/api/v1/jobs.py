from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.models.user import User
from app.workers.celery_app import celery_app

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


@router.get("/{job_id}")
async def get_job_detail(job_id: str, user: User = Depends(get_current_user)):
    """Get status of a specific Celery task."""
    result = celery_app.AsyncResult(job_id)
    return {
        "job_id": job_id,
        "status": result.status,
        "result": result.result if result.ready() else None,
    }
