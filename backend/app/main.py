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

    # Auto-scan library on startup in a background thread
    def _startup_scan():
        try:
            logging.basicConfig(level=logging.INFO)
            Base.metadata.create_all(bind=sync_engine)
            user_id = _get_or_create_admin_user()
            stats = scan_library(user_id=user_id)
            logger.info("Startup scan results: %s", stats)

            # Run face detection if new photos were indexed
            if stats.get("new_indexed", 0) > 0:
                from app.services.face_detector import process_all_photos
                from app.services.face_cluster import cluster_faces
                face_stats = process_all_photos(user_id=user_id)
                logger.info("Startup face detection: %s", face_stats)
                if face_stats.get("total_faces", 0) > 0:
                    cluster_stats = cluster_faces(user_id)
                    logger.info("Startup clustering: %s", cluster_stats)
            else:
                # Even if no new photos, re-cluster if faces are unlinked
                # (can happen if previous reprocess ran without clustering)
                from sqlalchemy import select as _select
                from app.models.face import Face as _Face
                from app.core.database import get_sync_db as _get_sync_db
                db_check = _get_sync_db()
                try:
                    unlinked = db_check.execute(
                        _select(_Face).where(
                            _Face.person_id.is_(None),
                            _Face.photo.has(user_id=user_id),
                        ).limit(1)
                    ).scalar_one_or_none()
                finally:
                    db_check.close()
                if unlinked is not None:
                    from app.services.face_cluster import cluster_faces
                    logger.info("Found unlinked faces — running clustering")
                    cluster_stats = cluster_faces(user_id)
                    logger.info("Startup clustering (repair): %s", cluster_stats)

            # Reverse-geocode photos with GPS but no location
            from app.services.geocoder import geocode_all_photos
            geo_stats = geocode_all_photos(user_id=user_id)
            logger.info("Startup geocoding: %s", geo_stats)
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
    """Trigger a full library scan + face detection + clustering (admin only). Runs in the background."""
    from app.services.scanner import scan_library
    from app.services.face_detector import process_all_photos
    from app.services.face_cluster import cluster_faces
    from app.services.geocoder import geocode_all_photos

    def _scan_and_detect(uid: str):
        scan_library(user_id=uid)
        face_stats = process_all_photos(user_id=uid)
        if face_stats.get("total_faces", 0) > 0:
            cluster_faces(uid)
        geocode_all_photos(user_id=uid)

    background_tasks.add_task(_scan_and_detect, str(user.id))
    return {"message": "Library scan started (includes face detection)", "status": "running"}


@app.post("/api/v1/rescan-faces")
async def rescan_faces(
    background_tasks: BackgroundTasks,
    user: User = Depends(require_admin),
):
    """Re-detect all faces with improved embeddings and re-cluster (admin only)."""
    from app.services.face_detector import reprocess_all_photos
    from app.services.face_cluster import cluster_faces

    def _rescan(uid: str):
        face_stats = reprocess_all_photos(user_id=uid)
        logger.info("Face reprocessing: %s", face_stats)
        if face_stats.get("total_faces", 0) > 0:
            cluster_stats = cluster_faces(uid)
            logger.info("Re-clustering: %s", cluster_stats)

    background_tasks.add_task(_rescan, str(user.id))
    return {"message": "Face re-scan started (reprocess + recluster)", "status": "running"}


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
