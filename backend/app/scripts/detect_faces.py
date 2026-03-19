"""
Run face detection on all photos that haven't been processed yet.

Usage:
    docker compose exec backend python -m app.scripts.detect_faces
"""
import logging
import sys

logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

import app.models  # noqa: F401 — registers all models before mapper config
from app.services.face_detector import process_all_photos

if __name__ == "__main__":
    stats = process_all_photos()
    print("Face detection complete:", stats)
    sys.exit(0)
