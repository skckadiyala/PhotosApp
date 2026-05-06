"""
PhotosApp — Phase 1: Core Backend + Photo Serving
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.core.database import engine
from app.api.v1.router import api_router
from app.api.deps import require_admin
from app.models.user import User

logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    import threading
    from app.services.scanner import scan_library, _get_or_create_admin_user
    from app.models import Base
    from app.core.database import sync_engine

    logger.info("Starting PhotosApp backend...")
    logger.info("Photos dir: %s", settings.photos_dir)
    logger.info("Thumbnails dir: %s", settings.thumbnails_dir)

    # Auto-scan library on startup in a background thread.
    # Intentionally lightweight: only index new files and geocode a small
    # batch. Face detection and clustering are NOT run on startup because
    # they are too slow for large libraries (100K+ photos). Use the manual
    # POST /api/v1/scan endpoint or the per-upload pipeline instead.
    def _startup_scan():
        try:
            logging.basicConfig(level=logging.INFO)
            Base.metadata.create_all(bind=sync_engine)
            user_id = _get_or_create_admin_user()
            stats = scan_library(user_id=user_id)
            logger.info("Startup scan results: %s", stats)

            # Dispatch up to 200 geocoding tasks — non-blocking, rate-limited
            # via Celery countdown so the startup thread is freed immediately.
            try:
                from app.workers.tasks.geocoder import dispatch_geocode_batch
                geo_stats = dispatch_geocode_batch(user_id=user_id, max_batch=200)
                logger.info("Startup geocoding dispatched: %s", geo_stats)
            except Exception:
                logger.warning("Could not dispatch geocoding batch", exc_info=True)

            # Rebuild event cluster materialization so the All Photos view
            # is fast immediately after startup without waiting for a manual scan.
            try:
                from app.workers.tasks.cluster import rebuild_clusters
                rebuild_clusters.delay(user_id)
                logger.info("Cluster rebuild queued after startup scan")
            except Exception:
                logger.warning("Could not dispatch startup cluster rebuild", exc_info=True)
        except Exception:
            logger.error("Startup scan failed", exc_info=True)

    threading.Thread(target=_startup_scan, daemon=True).start()

    yield
    await engine.dispose()
    logger.info("PhotosApp backend shut down.")


app = FastAPI(
    title="PhotosApp API",
    version="0.1.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# CORS — allow frontend dev server and production
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://localhost:80",
        "http://localhost",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routes
app.include_router(api_router, prefix="/api/v1")


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}


@app.post("/api/v1/scan")
async def trigger_scan(
    background_tasks: BackgroundTasks,
    user: User = Depends(require_admin),
):
    """Trigger a full library scan (admin only).

    New files get DB records inserted and their processing pipeline
    (thumbnails, metadata, face detection) dispatched to Celery workers.
    Geocoding is dispatched as Celery tasks so the scan thread is not blocked.
    """
    from app.services.scanner import scan_library
    from app.workers.tasks.geocoder import dispatch_geocode_batch

    def _scan(uid: str):
        scan_library(user_id=uid)
        dispatch_geocode_batch(user_id=uid, max_batch=500)
        # Rebuild event cluster materialization after scan so the All Photos
        # view reads pre-computed rows instead of running the 7-CTE chain.
        try:
            from app.workers.tasks.cluster import rebuild_clusters
            rebuild_clusters.delay(uid)
        except Exception:
            logger.warning("Could not dispatch cluster rebuild after scan", exc_info=True)

    background_tasks.add_task(_scan, str(user.id))
    return {"message": "Library scan started — processing dispatched to workers", "status": "running"}


@app.post("/api/v1/rebuild-clusters")
async def rebuild_clusters_endpoint(
    user: User = Depends(require_admin),
):
    """Rebuild the event cluster materialization table (admin only).

    Triggers a Celery task that re-computes all cluster assignments for this
    user and persists them to photo_clusters.  The All Photos / All Videos views
    will read the updated table on the next request.
    """
    from app.workers.tasks.cluster import rebuild_clusters
    rebuild_clusters.delay(str(user.id))
    return {"message": "Cluster rebuild queued — All Photos view will update shortly", "status": "running"}


@app.post("/api/v1/rescan-faces")
async def rescan_faces(
    user: User = Depends(require_admin),
):
    """Queue bulk face detection + clustering in the dedicated face_worker container."""
    from app.workers.tasks.faces import run_bulk_face_scan
    run_bulk_face_scan.delay(str(user.id))
    return {"message": "Face scan queued — running in face_worker container", "status": "running"}


@app.post("/api/v1/refresh-video-metadata")
async def refresh_video_metadata(
    background_tasks: BackgroundTasks,
    user: User = Depends(require_admin),
):
    """Re-extract taken_at / dimensions for video files that have NULL metadata (admin only)."""
    import os as _os
    from app.core.database import get_sync_db
    from app.models.photo import Photo
    from sqlalchemy import select

    def _refresh(photos_dir: str):
        db = get_sync_db()
        try:
            import json as _json
            from datetime import datetime as _dt
            from app.services.exif import _extract_quicktime_metadata, _parse_date_from_filename

            # Load macOS APFS birthtime manifest written by scripts/export-video-dates.sh
            birthtime_map: dict[str, str] = {}
            dates_json_path = _os.path.join(photos_dir, '.video_creation_dates.json')
            if _os.path.exists(dates_json_path):
                try:
                    with open(dates_json_path) as jf:
                        birthtime_map = _json.load(jf)
                    logger.info("Loaded %d birthtime entries from .video_creation_dates.json", len(birthtime_map))
                except Exception:
                    logger.warning("Could not read .video_creation_dates.json", exc_info=True)

            videos = list(db.execute(
                select(Photo)
                .where(Photo.mime_type.like("video/%"))
            ).scalars().all())
            logger.info("Refreshing metadata for %d video(s)", len(videos))
            for photo in videos:
                abs_path = _os.path.join(photos_dir, photo.file_path)
                try:
                    # Priority 1: macOS APFS st_birthtime from host-side export script
                    if photo.file_path in birthtime_map:
                        photo.taken_at = _dt.strptime(birthtime_map[photo.file_path], '%Y-%m-%dT%H:%M:%S')
                    # Priority 2: Date encoded in the filename (e.g. Clips24-06-10_23-03.mov)
                    else:
                        fn_date = _parse_date_from_filename(photo.file_name)
                        if fn_date:
                            photo.taken_at = fn_date
                        # Priority 3: mvhd atom (may reflect copy date, but better than nothing)
                        elif not photo.taken_at:
                            vm = _extract_quicktime_metadata(abs_path)
                            if vm.get("taken_at"):
                                photo.taken_at = vm["taken_at"]

                    if not photo.width:
                        vm = _extract_quicktime_metadata(abs_path)
                        if vm.get("width"):
                            photo.width = vm["width"]
                            photo.height = vm["height"]
                except Exception:
                    logger.warning("Metadata refresh failed for %s", photo.file_name, exc_info=True)
            db.commit()
            logger.info("Video metadata refresh complete")
        finally:
            db.close()

    background_tasks.add_task(_refresh, settings.photos_dir)
    return {"message": "Video metadata refresh started", "status": "running"}
