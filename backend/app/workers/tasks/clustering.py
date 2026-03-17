import logging

import numpy as np
from sklearn.cluster import DBSCAN

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="cluster_faces", bind=True)
def cluster_faces(self, embeddings_with_ids: list[dict]):
    """Run DBSCAN clustering on face embeddings."""
    if not embeddings_with_ids:
        return {"clusters": []}

    face_ids = [item["face_id"] for item in embeddings_with_ids]
    embeddings = np.array([item["embedding"] for item in embeddings_with_ids])

    # Normalize embeddings
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1, norms)
    embeddings_normalized = embeddings / norms

    # DBSCAN with cosine distance
    clustering = DBSCAN(
        eps=0.5,
        min_samples=2,
        metric="cosine",
    ).fit(embeddings_normalized)

    labels = clustering.labels_
    n_clusters = len(set(labels)) - (1 if -1 in labels else 0)

    results = [
        {"face_id": face_id, "cluster_id": int(label)}
        for face_id, label in zip(face_ids, labels)
    ]

    logger.info("Clustered %d faces into %d groups (%d noise)", len(face_ids), n_clusters, (labels == -1).sum())
    return {"clusters": results, "n_clusters": n_clusters}
