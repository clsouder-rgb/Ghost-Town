import logging
import time
from pathlib import Path
from queue import Queue, Empty
from threading import Thread

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileMovedEvent

from .config import WATCH_DIR, VIDEO_EXTENSIONS, IMAGE_EXTENSIONS
from .pipeline import process_file

logger = logging.getLogger(__name__)

SUPPORTED = VIDEO_EXTENSIONS | IMAGE_EXTENSIONS
SETTLE_SECONDS = 2.0  # wait for file to finish writing before processing


class _MediaHandler(FileSystemEventHandler):
    def __init__(self, queue: Queue):
        self._queue = queue

    def on_created(self, event: FileCreatedEvent):
        if not event.is_directory:
            self._enqueue(event.src_path)

    def on_moved(self, event: FileMovedEvent):
        if not event.is_directory:
            self._enqueue(event.dest_path)

    def _enqueue(self, path: str):
        p = Path(path)
        if p.suffix.lower() in SUPPORTED:
            logger.info(f"Detected: {p.name}")
            self._queue.put(p)


def _worker(queue: Queue, drive_sync: bool, stop_flag: list):
    while not stop_flag[0]:
        try:
            file_path: Path = queue.get(timeout=1)
        except Empty:
            continue

        # Wait for the file to settle (finish copying/downloading)
        _wait_for_stable(file_path)

        if not file_path.exists():
            logger.warning(f"File disappeared before processing: {file_path}")
            queue.task_done()
            continue

        logger.info(f"Processing: {file_path.name}")
        try:
            result = process_file(file_path, drive_sync=drive_sync)
            _log_result(result)
        except Exception as exc:
            logger.error(f"Pipeline error for {file_path.name}: {exc}", exc_info=True)
        finally:
            queue.task_done()


def _wait_for_stable(path: Path, interval: float = 0.5, stable_rounds: int = 4):
    prev_size = -1
    rounds = 0
    while rounds < stable_rounds:
        try:
            current_size = path.stat().st_size
        except FileNotFoundError:
            return
        if current_size == prev_size:
            rounds += 1
        else:
            rounds = 0
        prev_size = current_size
        time.sleep(interval)


def _log_result(result: dict):
    if result.get("error"):
        logger.error(f"  Error: {result['error']}")
        return
    score = result.get("viability_score", "N/A")
    md = result.get("md_path", "")
    docx = result.get("docx_path", "")
    urls = result.get("drive_urls", {})
    logger.info(f"  Viability: {score}/10")
    logger.info(f"  MD:   {md}")
    logger.info(f"  DOCX: {docx}")
    for name, url in urls.items():
        logger.info(f"  Drive [{name}]: {url}")


class OrneryKiwiWatcher:
    """Main watcher class. Call .start() to begin watching, .stop() to halt."""

    def __init__(self, watch_dir: Path = WATCH_DIR, drive_sync: bool = True):
        self.watch_dir = Path(watch_dir)
        self.drive_sync = drive_sync
        self._queue: Queue = Queue()
        self._stop_flag = [False]
        self._observer = None
        self._worker_thread = None

    def start(self):
        self.watch_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Ornery-Kiwi watching: {self.watch_dir}")

        handler = _MediaHandler(self._queue)
        self._observer = Observer()
        self._observer.schedule(handler, str(self.watch_dir), recursive=False)
        self._observer.start()

        self._worker_thread = Thread(
            target=_worker,
            args=(self._queue, self.drive_sync, self._stop_flag),
            daemon=True,
        )
        self._worker_thread.start()
        logger.info("Ornery-Kiwi ready. Drop media files into the watch folder.")

    def stop(self):
        self._stop_flag[0] = True
        if self._observer:
            self._observer.stop()
            self._observer.join()
        if self._worker_thread:
            self._worker_thread.join(timeout=5)
        logger.info("Ornery-Kiwi stopped.")

    def process_existing(self):
        """Scan watch_dir for existing files and queue them immediately."""
        for p in sorted(self.watch_dir.iterdir()):
            if p.suffix.lower() in SUPPORTED and p.is_file():
                logger.info(f"Queuing existing file: {p.name}")
                self._queue.put(p)
