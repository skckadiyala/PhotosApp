"""
Face clustering service.

Uses Agglomerative Clustering with average linkage on face_recognition's
128-d embeddings, followed by a centroid-merge pass to combine clusters
that are close neighbours.  This produces significantly better grouping
than single-pass DBSCAN.
"""
import logging

import numpy as np
from sklearn.cluster import AgglomerativeClustering
from sqlalchemy import select

from app.core.database import get_sync_db
from app.models.face import Face
from app.models.person import Person

logger = logging.getLogger(__name__)

# ---------- Tunable thresholds ----------
# Primary clustering — Euclidean distance threshold for agglomerative clustering.
# face_recognition embeddings: same person typically < 0.6 Euclidean distance.
# A slightly tighter threshold avoids merging different people.
CLUSTER_THRESHOLD = 0.55

# Secondary merge — if two cluster centroids are within this Euclidean distance
# AND the max pairwise distance between any two faces in the merged cluster stays
# below MAX_INTRA_DISTANCE, they get merged.  This prevents chain-reaction merges.
MERGE_THRESHOLD = 0.55
MAX_INTRA_DISTANCE = 0.68

# Faces with distance-to-centroid above this are flagged as "pending" for user review.
CONFIRM_THRESHOLD = 0.32


def _merge_close_clusters(
    labels: np.ndarray,
    embeddings: np.ndarray,
    threshold: float,
    max_intra: float,
) -> np.ndarray:
    """
    Post-clustering pass: merge clusters whose centroids are within *threshold*
    Euclidean distance, but only if the merged cluster's max pairwise distance
    stays below *max_intra*.  This prevents chain-reaction merges that collapse
    everything into a single cluster.
    """
    changed = True
    while changed:
        changed = False
        unique = sorted(set(labels))
        centroids = {}
        for lbl in unique:
            mask = labels == lbl
            centroids[lbl] = embeddings[mask].mean(axis=0)

        for i, a in enumerate(unique):
            for b in unique[i + 1:]:
                dist = np.linalg.norm(centroids[a] - centroids[b])
                if dist < threshold:
                    # Check max intra-cluster distance after hypothetical merge
                    mask_a = labels == a
                    mask_b = labels == b
                    merged_embs = embeddings[mask_a | mask_b]
                    # Compute pairwise max distance
                    from scipy.spatial.distance import pdist
                    max_pdist = pdist(merged_embs, metric="euclidean").max()
                    if max_pdist < max_intra:
                        logger.debug(
                            "Merging cluster %d into %d (centroid dist=%.3f, max_intra=%.3f)",
                            b, a, dist, max_pdist,
                        )
                        labels[labels == b] = a
                        changed = True
                        break
                    else:
                        logger.debug(
                            "Skipping merge %d+%d (centroid dist=%.3f OK but max_intra=%.3f > %.3f)",
                            a, b, dist, max_pdist, max_intra,
                        )
            if changed:
                break

    # Re-number labels to be contiguous 0..N-1
    unique = sorted(set(labels))
    mapping = {old: new for new, old in enumerate(unique)}
    return np.array([mapping[l] for l in labels])


def cluster_faces(user_id: str) -> dict:
    """
    Cluster all face embeddings into Person groups using Agglomerative
    Clustering with cosine distance, then merge close centroids.

    Every face is assigned to a cluster (no "noise" faces lost).

    Returns:
        Stats dict: {total_faces, clusters_created, clusters_merged}
    """
    db = get_sync_db()
    stats = {"total_faces": 0, "clusters_created": 0, "clusters_merged": 0}

    try:
        face_rows = db.execute(
            select(Face)
            .join(Face.photo)
            .where(Face.photo.has(user_id=user_id))
        ).scalars().all()

        if not face_rows:
            logger.info("No faces found for user %s", user_id)
            return stats

        stats["total_faces"] = len(face_rows)
        embeddings = np.array([f.embedding for f in face_rows])

        # --- Phase 1: Agglomerative Clustering ---
        # Use Euclidean distance on raw embeddings (face_recognition's native metric)
        if len(face_rows) == 1:
            labels = np.array([0])
        else:
            agg = AgglomerativeClustering(
                n_clusters=None,
                distance_threshold=CLUSTER_THRESHOLD,
                metric="euclidean",
                linkage="average",
            )
            labels = agg.fit_predict(embeddings)

        initial_clusters = len(set(labels))
        logger.info(
            "Phase 1 — agglomerative clustering: %d faces → %d clusters (threshold=%.2f)",
            len(embeddings), initial_clusters, CLUSTER_THRESHOLD,
        )

        # --- Phase 2: Centroid-merge pass ---
        labels = _merge_close_clusters(labels, embeddings, MERGE_THRESHOLD, MAX_INTRA_DISTANCE)
        final_clusters = len(set(labels))
        stats["clusters_merged"] = initial_clusters - final_clusters

        logger.info(
            "Phase 2 — centroid merge: %d → %d clusters (merged %d, threshold=%.2f)",
            initial_clusters, final_clusters, stats["clusters_merged"], MERGE_THRESHOLD,
        )

        # --- Persist results ---
        # Capture existing names BEFORE clearing assignments, keyed by centroid
        # of the faces currently linked to each named person.  Falls back to any
        # face embedding when only one face is linked.
        existing_people = db.execute(
            select(Person).where(Person.user_id == user_id)
        ).scalars().all()

        old_names: dict[str, np.ndarray] = {}
        for person in existing_people:
            if person.name:
                linked_faces = db.execute(
                    select(Face).where(Face.person_id == person.id)
                ).scalars().all()
                if linked_faces:
                    centroid = np.array([f.embedding for f in linked_faces]).mean(axis=0)
                    old_names[person.name] = centroid

        # Now clear old person assignments and delete old Person records
        for face in face_rows:
            face.person_id = None
        db.flush()

        for person in existing_people:
            db.delete(person)
        db.flush()

        # Create new Person per cluster
        unique_labels = sorted(set(labels))
        cluster_map: dict[int, Person] = {}
        for label in unique_labels:
            person = Person(user_id=user_id, face_count=0)
            db.add(person)
            db.flush()
            cluster_map[label] = person
            stats["clusters_created"] += 1

        # Compute centroids per cluster for distance scoring
        cluster_centroids: dict[int, np.ndarray] = {}
        for label in unique_labels:
            mask = labels == label
            cluster_centroids[label] = embeddings[mask].mean(axis=0)

        # Assign faces and compute match_distance + status
        for face, label, emb in zip(face_rows, labels, embeddings):
            face.person_id = cluster_map[label].id
            dist = float(np.linalg.norm(emb - cluster_centroids[label]))
            face.match_distance = dist
            # Faces far from centroid are flagged for user review
            face.status = "pending" if dist > CONFIRM_THRESHOLD else "confirmed"

        # Update face counts
        for label, person in cluster_map.items():
            person.face_count = int(np.sum(labels == label))

        # Attempt to re-assign old names to new clusters by embedding proximity
        if old_names:
            for label, person in cluster_map.items():
                mask = labels == label
                centroid = embeddings[mask].mean(axis=0)
                best_name = None
                best_dist = float("inf")
                for name, emb in old_names.items():
                    d = np.linalg.norm(centroid - emb)
                    if d < best_dist:
                        best_dist = d
                        best_name = name
                if best_name and best_dist < MERGE_THRESHOLD:
                    person.name = best_name
                    # Remove so each name is used only once
                    del old_names[best_name]

        db.commit()
        logger.info(
            "Clustering complete: %d faces → %d clusters (%d merged)",
            stats["total_faces"], stats["clusters_created"], stats["clusters_merged"],
        )

    except Exception:
        logger.error("Clustering failed", exc_info=True)
        db.rollback()
        raise
    finally:
        db.close()

    return stats


def merge_people(person_id_keep: str, person_id_merge: str, user_id: str) -> dict:
    """
    Merge two Person clusters: move all faces from person_id_merge into person_id_keep,
    then delete person_id_merge.

    Args:
        person_id_keep: UUID of the person to keep.
        person_id_merge: UUID of the person to merge into keep.
        user_id: UUID of the user (for ownership check).

    Returns:
        Stats dict with faces_moved count.
    """
    db = get_sync_db()

    try:
        keep = db.execute(
            select(Person).where(Person.id == person_id_keep, Person.user_id == user_id)
        ).scalar_one_or_none()
        merge = db.execute(
            select(Person).where(Person.id == person_id_merge, Person.user_id == user_id)
        ).scalar_one_or_none()

        if not keep or not merge:
            raise ValueError("One or both person IDs not found")
        if keep.id == merge.id:
            raise ValueError("Cannot merge a person with itself")

        # Move faces
        faces_to_move = db.execute(
            select(Face).where(Face.person_id == person_id_merge)
        ).scalars().all()

        for face in faces_to_move:
            face.person_id = person_id_keep

        # Update counts
        keep.face_count += len(faces_to_move)

        # Keep the name if keep doesn't have one
        if not keep.name and merge.name:
            keep.name = merge.name

        # Delete merged person
        db.delete(merge)
        db.commit()

        logger.info("Merged person %s into %s (%d faces moved)",
                     person_id_merge, person_id_keep, len(faces_to_move))
        return {"faces_moved": len(faces_to_move)}

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main():
    """CLI entry point for face clustering."""
    import sys
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    from app.core.database import sync_engine, get_sync_db
    from app.models import Base
    from app.models.user import User

    Base.metadata.create_all(bind=sync_engine)

    # Get admin user
    db = get_sync_db()
    user = db.execute(select(User).where(User.role == "admin")).scalar_one_or_none()
    db.close()

    if not user:
        print("No admin user found. Run seed first.")
        sys.exit(1)

    stats = cluster_faces(str(user.id))
    print(f"\nClustering results: {stats}")


if __name__ == "__main__":
    main()
