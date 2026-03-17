import logging
import os

import numpy as np

from app.config import get_settings
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)
settings = get_settings()

# Lazy-loaded model
_face_app = None


def _get_face_app():
    global _face_app
    if _face_app is None:
        from insightface.app import FaceAnalysis
        _face_app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
        _face_app.prepare(ctx_id=0, det_size=(640, 640))
    return _face_app


@celery_app.task(name="detect_faces", bind=True, max_retries=2)
def detect_faces(self, photo_id: str, file_path: str):
    """Detect faces and extract 512-dim embeddings."""
    try:
        import cv2

        full_path = os.path.join(settings.photos_dir, file_path)
        if not os.path.isfile(full_path):
            logger.error("Photo file not found: %s", full_path)
            return None

        img = cv2.imread(full_path)
        if img is None:
            logger.error("Could not read image: %s", full_path)
            return None

        app = _get_face_app()
        detected = app.get(img)

        faces = []
        for face in detected:
            bbox = face.bbox.astype(int)
            embedding = face.embedding.tolist()

            faces.append({
                "photo_id": photo_id,
                "bbox_x": int(bbox[0]),
                "bbox_y": int(bbox[1]),
                "bbox_w": int(bbox[2] - bbox[0]),
                "bbox_h": int(bbox[3] - bbox[1]),
                "embedding": embedding,
                "confidence": float(face.det_score),
            })

        logger.info("Detected %d faces in photo %s", len(faces), photo_id)
        return {"photo_id": photo_id, "faces": faces}

    except Exception as exc:
        logger.exception("Face detection failed for %s", photo_id)
        raise self.retry(exc=exc, countdown=60)
