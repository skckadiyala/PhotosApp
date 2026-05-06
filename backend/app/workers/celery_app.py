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
        # Module-path globs (matched when task is called via module, not registered name)
        "app.workers.tasks.thumbnail.*": {"queue": "thumbnails"},
        "app.workers.tasks.metadata.*": {"queue": "metadata"},
        "app.workers.tasks.faces.*": {"queue": "faces"},
        "app.workers.tasks.tagging.*": {"queue": "tagging"},
        "app.workers.tasks.cluster.*": {"queue": "metadata"},
        "app.workers.tasks.geocoder.*": {"queue": "metadata"},
        # Explicit registered task-name routes (used when task is dispatched by name)
        "generate_thumbnails": {"queue": "thumbnails"},
        "extract_metadata": {"queue": "metadata"},
        "detect_faces": {"queue": "faces"},
        "auto_tag_photo": {"queue": "tagging"},
        "rebuild_clusters": {"queue": "metadata"},
        "geocode_photo": {"queue": "metadata"},
    },
    task_default_queue="metadata",
)

# Auto-discover task modules
celery_app.autodiscover_tasks([
    "app.workers.tasks.thumbnail",
    "app.workers.tasks.metadata",
    "app.workers.tasks.faces",
    "app.workers.tasks.tagging",
    "app.workers.tasks.cluster",
    "app.workers.tasks.geocoder",
])
