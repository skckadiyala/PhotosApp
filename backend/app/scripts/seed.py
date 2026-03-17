"""
Seed script — creates the initial admin user and ensures tables exist.

Run via:
    python -m app.scripts.seed
    # or inside Docker:
    docker compose exec backend python -m app.scripts.seed
"""
import logging
import sys

from sqlalchemy import select

from app.config import get_settings
from app.core.database import get_sync_db, sync_engine
from app.core.security import hash_password
from app.models import Base
from app.models.user import User

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)
settings = get_settings()


def seed():
    # Ensure all tables exist
    Base.metadata.create_all(bind=sync_engine)
    logger.info("Database tables ensured.")

    db = get_sync_db()
    try:
        # Check if admin already exists
        result = db.execute(select(User).where(User.username == settings.admin_username))
        existing = result.scalar_one_or_none()
        if existing:
            logger.info("Admin user '%s' already exists (id=%s)", existing.username, existing.id)
            return

        user = User(
            username=settings.admin_username,
            email=settings.admin_email,
            password_hash=hash_password(settings.admin_password),
            role="admin",
        )
        db.add(user)
        db.commit()
        logger.info("Created admin user: %s (id=%s)", user.username, user.id)
    except Exception:
        db.rollback()
        logger.exception("Failed to seed database")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    seed()
