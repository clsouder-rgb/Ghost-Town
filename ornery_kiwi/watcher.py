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

MEDIA_SUPPORTED = VIDEO_EXTENSIONS | IMAGE_EXTENSIONS
# Document types routed to Evidence Library ingest
try:
    from evidence_library.extractors import SUPPORTED_EXTENSIONS as _DOC_EXT
    DOC_SUPPORTED = _DOC_EXT
except Exception:
    DOC_SUPPORTED = {".pdf", ".docx", ".txt", ".md", ".text"}

ALL_SUPPORTED = MEDIA_SUPPORTED | DOC_SUPPORTED
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
        suffix = p.suffix.lower()
        if suffix in ALL_SUPPORTED:
            kind = "doc" if suffix in DOC_SUPPORTED else "media"
            logger.info(f"Detected {kind}: {p.name}")
            self._queue.put(p)


def _ingest_document(file_path: Path):
    """Route a dropped document file into the Evidence Library."""
    try:
        import os
        if os.getenv("EVIDENCE_INGEST_DISABLED"):
            logger.info(f"[EvidenceLibrary] Auto-ingest disabled, skipping {file_path.name}")
            return
        from evidence_library.extractors import extract_text, infer_metadata
        from evidence_library.ingest import ingest_text_document
        from evidence_library import db
        from ornery_kiwi.config import BASE_DIR
        db.init_db(BASE_DIR / "evidence.db")

        text, err = extract_text(file_path)
        if err or not text.strip():
            logger.warning(f"[EvidenceLibrary] Could not extract text from {file_path.name}: {err}")
            return

        meta = infer_metadata(text, file_path.name)
        record = ingest_text_document(
            title=meta["title"],
            content=text,
            source_type="other",
            source_path=str(file_path),
            tags=[],
            citation=str(file_path),
            population_topic=meta.get("population_topic"),
            confidence_flag="unknown",
        )
        logger.info(f"[EvidenceLibrary] Ingested: {record.title[:60]}  id={record.id[:8]}")
    except Exception as exc:
        logger.warning(f"[EvidenceLibrary] Ingest failed for {file_path.name}: {exc}")


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

        suffix = file_path.suffix.lower()
        if suffix in DOC_SUPPORTED:
            logger.info(f"Ingesting document: {file_path.name}")
            try:
                _ingest_document(file_path)
            except Exception as exc:
                logger.error(f"Document ingest error for {file_path.name}: {exc}", exc_info=True)
        else:
            logger.info(f"Processing media: {file_path.name}")
            try:
                result = process_file(file_path, drive_sync=drive_sync)
                _log_result(result)
            except Exception as exc:
                logger.error(f"Pipeline error for {file_path.name}: {exc}", exc_info=True)
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
            if p.suffix.lower() in ALL_SUPPORTED and p.is_file():
                logger.info(f"Queuing existing file: {p.name}")
                self._queue.put(p)
