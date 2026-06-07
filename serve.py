#!/usr/bin/env python3
"""
Ornery-Kiwi unified server.
Starts the FastAPI API on port 8000 AND the folder watcher in a daemon thread.

  python serve.py [--no-drive] [--no-watch] [--host HOST] [--port PORT]
"""

import argparse
import logging
import sys
import threading

import uvicorn

from ornery_kiwi.config import WATCH_DIR, BASE_DIR, OUTPUT_DIR, PROCESSED_DIR, API_HOST, API_PORT


def _ensure_dirs():
    for d in [BASE_DIR, WATCH_DIR, OUTPUT_DIR, PROCESSED_DIR]:
        d.mkdir(parents=True, exist_ok=True)


def _start_watcher(drive_sync: bool):
    from ornery_kiwi.watcher import OrneryKiwiWatcher
    watcher = OrneryKiwiWatcher(watch_dir=WATCH_DIR, drive_sync=drive_sync)
    watcher.start()
    watcher.process_existing()

    import time
    try:
        while True:
            time.sleep(60)
    except Exception:
        watcher.stop()


def main():
    parser = argparse.ArgumentParser(prog="serve", description="Ornery-Kiwi server")
    parser.add_argument("--host", default=API_HOST, help=f"API host (default: {API_HOST})")
    parser.add_argument("--port", type=int, default=API_PORT, help=f"API port (default: {API_PORT})")
    parser.add_argument("--no-drive", action="store_true", help="Skip Google Drive sync")
    parser.add_argument("--no-watch", action="store_true", help="Disable folder watcher")
    parser.add_argument("--reload", action="store_true", help="Hot-reload (dev only)")
    parser.add_argument("--log-level", default="info")
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )
    for noisy in ("httpx", "urllib3", "googleapiclient", "google"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _ensure_dirs()

    if not args.no_watch:
        drive_sync = not args.no_drive
        watcher_thread = threading.Thread(
            target=_start_watcher,
            args=(drive_sync,),
            daemon=True,
            name="ornery-kiwi-watcher",
        )
        watcher_thread.start()
        logging.getLogger(__name__).info(f"Folder watcher started on {WATCH_DIR}")

    from ornery_kiwi.api.app import app
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level=args.log_level,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
