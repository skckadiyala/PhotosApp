from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "photosapp",
    broker=settings.celery_broker_url,
    backend=settings.celery_broker_url.replace("/0", "/1"),
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "app.workers.tasks.thumbnail.*": {"queue": "thumbnails"},
        "app.workers.tasks.metadata.*": {"queue": "metadata"},
        "app.workers.tasks.faces.*": {"queue": "faces"},
        "app.workers.tasks.tagging.*": {"queue": "tagging"},
    },
    task_default_queue="metadata",
)

# Auto-discover task modules
celery_app.autodiscover_tasks([
    "app.workers.tasks.thumbnail",
    "app.workers.tasks.metadata",
    "app.workers.tasks.faces",
    "app.workers.tasks.tagging",
])
