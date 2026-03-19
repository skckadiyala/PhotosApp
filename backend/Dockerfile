# ── Build stage ──────────────────────────────────────────────
FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip setuptools && \
    pip install --no-cache-dir . && \
    pip install --no-cache-dir opencv-python-headless --force-reinstall

COPY . .

# Pre-download DeepFace model weights so containers don't need internet
# access on first run.  The directory is created unconditionally so the
# COPY in the production stage never fails even if download is skipped.
RUN mkdir -p /root/.deepface/weights && \
    python -c "\
import numpy as np; \
from deepface import DeepFace; \
dummy = np.random.randint(0, 255, (300, 300, 3), dtype=np.uint8); \
try: DeepFace.represent(img_path=dummy, model_name='ArcFace', detector_backend='retinaface', enforce_detection=True) \
except Exception: pass" 2>/dev/null || true

# ── Production stage ────────────────────────────────────────
FROM python:3.12-slim AS production

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /app /app
# Copy pre-downloaded model weights from build stage
COPY --from=builder /root/.deepface /root/.deepface

RUN mkdir -p /data/thumbnails

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
