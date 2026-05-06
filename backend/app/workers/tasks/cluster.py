import logging

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="rebuild_clusters", bind=True, max_retries=2)
def rebuild_clusters(self, user_id: str, gap_hours: int = 6):
    """Rebuild event cluster materialization for a user (both image and video).

    Runs in the metadata queue so it doesn't compete with thumbnail generation.
    Triggered automatically after a library scan completes.
    """
    try:
        from app.services.cluster_builder import rebuild_all_clusters
        stats = rebuild_all_clusters(user_id, gap_hours=gap_hours)
        logger.info("Cluster rebuild complete for user %s: %s", user_id, stats)
        return stats
    except Exception as exc:
        logger.exception("Cluster rebuild failed for user %s", user_id)
        raise self.retry(exc=exc, countdown=120)
