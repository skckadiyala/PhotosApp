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
from app.api.deps import get_current_user, require_admin
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

            # Run face detection + clustering if new photos were indexed
            if stats.get("new_indexed", 0) > 0:
                from app.services.face_detector import process_all_photos
                from app.services.face_cluster import cluster_faces
                face_stats = process_all_photos(user_id=user_id)
                logger.info("Startup face detection: %s", face_stats)
                if face_stats.get("total_faces", 0) > 0:
                    cluster_stats = cluster_faces(user_id)
                    logger.info("Startup clustering: %s", cluster_stats)

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
