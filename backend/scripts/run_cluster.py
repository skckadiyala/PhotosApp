import logging
import sys

logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

import numpy as np
from scipy.spatial.distance import pdist
import app.models  # noqa: F401
from app.core.database import get_sync_db
from app.models.face import Face
from app.models.user import User
from app.services.face_cluster import cluster_faces
from sqlalchemy import select

db = get_sync_db()
users = db.execute(select(User)).scalars().all()

# Sample distances to show calibration info
faces_sample = db.execute(select(Face).limit(100)).scalars().all()
if faces_sample:
    embs = np.array([f.embedding for f in faces_sample])
    norms = np.linalg.norm(embs, axis=1)
    dists = pdist(embs, metric='euclidean')
    print(f"\nEmbedding norms: min={norms.min():.3f} max={norms.max():.3f} mean={norms.mean():.3f}")
    print(f"Pairwise Euclidean: min={dists.min():.3f} p5={np.percentile(dists,5):.3f} p25={np.percentile(dists,25):.3f} median={np.median(dists):.3f} p75={np.percentile(dists,75):.3f} max={dists.max():.3f}")

db.close()

for u in users:
    print(f"\nClustering faces for user: {u.email}")
    stats = cluster_faces(str(u.id))
    print(f"Result: {stats}")

