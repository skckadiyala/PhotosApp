"""
File system watcher that monitors the photos directory for new files
and dispatches them into the processing pipeline.
"""
import hashlib
import logging
import os
import sys
import time

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class PhotoEventHandler(FileSystemEventHandler):
    """Handle new photo files appearing in the watch directory."""

    def __init__(self):
        super().__init__()
        self._processing = set()

    def on_created(self, event):
        if event.is_directory:
            return
        self._handle_new_file(event.src_path)

    def on_moved(self, event):
        if event.is_directory:
            return
        self._handle_new_file(event.dest_path)

    def _handle_new_file(self, file_path: str):
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in settings.supported_extensions:
            return

        # Debounce: skip if already being processed
        if file_path in self._processing:
            return
        self._processing.add(file_path)

        # Wait for file to finish writing
        _wait_for_stable(file_path)

        try:
            rel_path = os.path.relpath(file_path, settings.photos_dir)
            file_hash = _compute_hash(file_path)
            file_size = os.path.getsize(file_path)
            file_name = os.path.basename(file_path)

            logger.info("New photo detected: %s (hash=%s, size=%d)", rel_path, file_hash, file_size)

            # Import here to avoid circular imports
            from app.workers.pipeline import dispatch_photo_pipeline

            dispatch_photo_pipeline(photo_id="pending", file_path=rel_path)

        except Exception:
            logger.exception("Error handling new file: %s", file_path)
        finally:
            self._processing.discard(file_path)


def _wait_for_stable(path: str, interval: float = 1.0, retries: int = 10):
    """Wait until file size stops changing (file finished copying)."""
    prev_size = -1
    for _ in range(retries):
        try:
            size = os.path.getsize(path)
            if size == prev_size and size > 0:
                return
            prev_size = size
        except OSError:
            pass
        time.sleep(interval)


def _compute_hash(path: str, chunk_size: int = 65536) -> str:
    """Compute SHA-256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            sha256.update(chunk)
    return sha256.hexdigest()


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    watch_dir = settings.photos_dir
    if not os.path.isdir(watch_dir):
        logger.error("Photos directory does not exist: %s", watch_dir)
        sys.exit(1)

    logger.info("Watching for new photos in: %s", watch_dir)

    handler = PhotoEventHandler()
    observer = Observer()
    observer.schedule(handler, watch_dir, recursive=True)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        logger.info("File watcher stopped.")
    observer.join()


if __name__ == "__main__":
    main()
