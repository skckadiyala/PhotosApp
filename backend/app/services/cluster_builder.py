"""
Event cluster materialization service.

Computes adaptive time-gap clusters for all visible photos/videos and writes
the results to the photo_clusters table.  The API reads from this table instead
of running the 7-CTE chain on every request.

Rebuild is triggered:
  - After each library scan completes (via Celery task)
  - On demand via POST /api/v1/rebuild-clusters (admin)

The gap_hours parameter controls how large a time gap starts a new cluster.
Default is 6 hours.  When the user changes this setting the rebuild detects
the stale gap_hours value and regenerates automatically.
"""
import logging
import time
from datetime import datetime, timezone

from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from app.core.database import get_sync_db
from app.models.photo import Photo

logger = logging.getLogger(__name__)

# Default gap for cluster rebuild — matches the frontend default
DEFAULT_GAP_HOURS = 6


def build_clusters(
    user_id: str,
    media_type: str = "image",
    gap_hours: int = DEFAULT_GAP_HOURS,
    db: Session | None = None,
) -> dict:
    """
    Compute event clusters and persist them to photo_clusters.

    Deletes existing rows for this (user_id, media_type, gap_hours) combination
    then inserts fresh cluster assignments in a single transaction.

    Returns stats dict: {clusters, photos_assigned, elapsed_s}
    """
    t0 = time.time()
    own_db = db is None
    if own_db:
        db = get_sync_db()

    try:
        mime_prefix = f"{media_type}/%"
        gap_seconds = gap_hours * 3600

        # ── Step 1: fetch all visible photos ordered by timestamp ─────────────
        rows = db.execute(
            text("""
                SELECT id, COALESCE(taken_at, created_at) AS ts, thumb_sm
                FROM photos
                WHERE user_id = :uid
                  AND is_hidden = false
                  AND mime_type LIKE :mime_prefix
                ORDER BY COALESCE(taken_at, created_at) DESC NULLS LAST, id
            """),
            {"uid": str(user_id), "mime_prefix": mime_prefix},
        ).fetchall()

        if not rows:
            return {"clusters": 0, "photos_assigned": 0, "elapsed_s": 0.0}

        # ── Step 2: assign cluster IDs by time gap ────────────────────────────
        cluster_id = 0
        assignments: list[dict] = []
        prev_ts: datetime | None = None

        for row in rows:
            ts: datetime | None = row.ts
            if prev_ts is not None and ts is not None:
                gap = (prev_ts - ts).total_seconds()
                if gap > gap_seconds:
                    cluster_id += 1
            elif prev_ts is None:
                cluster_id = 0

            assignments.append({
                "photo_id": str(row.id),
                "ts": ts,
                "cluster_id": cluster_id,
                "thumb_sm": row.thumb_sm,
            })
            if ts is not None:
                prev_ts = ts

        # ── Step 3: compute per-cluster aggregates ────────────────────────────
        from collections import defaultdict
        cluster_meta: dict[int, dict] = defaultdict(lambda: {
            "start": None, "end": None, "count": 0, "cover_photo_id": None, "cover_ts": None
        })

        for a in assignments:
            cid = a["cluster_id"]
            ts = a["ts"]
            meta = cluster_meta[cid]
            meta["count"] += 1

            if ts is not None:
                if meta["start"] is None or ts > meta["start"]:
                    meta["start"] = ts
                if meta["end"] is None or ts < meta["end"]:
                    meta["end"] = ts
                # Cover = the most recent photo in the cluster that has a thumbnail
                if a["thumb_sm"] and (meta["cover_ts"] is None or ts > meta["cover_ts"]):
                    meta["cover_ts"] = ts
                    meta["cover_photo_id"] = a["photo_id"]

        # ── Step 4: delete stale rows and insert fresh ones ───────────────────
        db.execute(
            text("""
                DELETE FROM photo_clusters
                WHERE user_id = :uid
                  AND media_type = :media_type
                  AND gap_hours = :gap_hours
            """),
            {"uid": str(user_id), "media_type": media_type, "gap_hours": gap_hours},
        )

        now = datetime.now(timezone.utc)

        insert_rows = []
        for a in assignments:
            cid = a["cluster_id"]
            meta = cluster_meta[cid]
            insert_rows.append({
                "photo_id": a["photo_id"],
                "user_id": str(user_id),
                "media_type": media_type,
                "gap_hours": gap_hours,
                "cluster_id": cid,
                "cluster_start": meta["start"],
                "cluster_end": meta["end"],
                "cluster_count": meta["count"],
                "is_cover": (a["photo_id"] == meta["cover_photo_id"]),
                "computed_at": now,
            })

        if insert_rows:
            db.execute(
                text("""
                    INSERT INTO photo_clusters
                        (photo_id, user_id, media_type, gap_hours, cluster_id,
                         cluster_start, cluster_end, cluster_count, is_cover, computed_at)
                    VALUES
                        (:photo_id, :user_id, :media_type, :gap_hours, :cluster_id,
                         :cluster_start, :cluster_end, :cluster_count, :is_cover, :computed_at)
                """),
                insert_rows,
            )

        db.commit()

        elapsed = time.time() - t0
        n_clusters = cluster_id + 1
        logger.info(
            "Cluster rebuild done: user=%s media=%s gap=%dh → %d clusters, %d photos in %.1fs",
            user_id, media_type, gap_hours, n_clusters, len(assignments), elapsed,
        )
        return {"clusters": n_clusters, "photos_assigned": len(assignments), "elapsed_s": round(elapsed, 2)}

    except Exception:
        db.rollback()
        logger.error("Cluster rebuild failed for user=%s media=%s", user_id, media_type, exc_info=True)
        raise
    finally:
        if own_db:
            db.close()


def rebuild_all_clusters(user_id: str, gap_hours: int = DEFAULT_GAP_HOURS) -> dict:
    """Rebuild clusters for both image and video media types."""
    results = {}
    for media_type in ("image", "video"):
        results[media_type] = build_clusters(user_id, media_type, gap_hours)
    return results
