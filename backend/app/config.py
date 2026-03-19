from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database (async for FastAPI)
    database_url: str = "postgresql+asyncpg://photosapp:photosapp@localhost:5432/photosapp"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Auth
    secret_key: str = "CHANGE-ME-IN-PRODUCTION"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # Paths
    photos_dir: str = "/mnt/photos"
    thumbnails_dir: str = "/data/thumbnails"
    host_photos_dir: str = ""  # actual path on the host machine, passed in via HOST_PHOTOS_DIR env var

    # Celery
    celery_broker_url: str = "redis://localhost:6379/0"

    # Admin seed
    admin_username: str = "admin"
    admin_email: str = "admin@photosapp.dev"
    admin_password: str = "admin"

    # Thumbnail sizes (px, longest edge)
    thumb_sm: int = 200
    thumb_md: int = 800
    thumb_lg: int = 1600

    # Supported image and video extensions
    supported_extensions: set[str] = {
        ".jpg", ".jpeg", ".png", ".gif", ".bmp",
        ".webp", ".tiff", ".tif", ".heic", ".heif",
        ".raw", ".cr2", ".nef", ".arw", ".dng",
        # Video
        ".mov", ".mp4", ".m4v", ".avi", ".mkv", ".webm", ".3gp",
    }

    @property
    def sync_database_url(self) -> str:
        """Sync DB URL for Celery workers and Alembic."""
        return self.database_url.replace("+asyncpg", "+psycopg2").replace(
            "postgresql+psycopg2", "postgresql+psycopg2"
        )

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
