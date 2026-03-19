import logging
import sys

logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

import app.models  # noqa: F401 — registers all models before mapper config
from app.services.face_detector import process_all_photos

stats = process_all_photos()
print("FACE DETECTION COMPLETE:", stats)
