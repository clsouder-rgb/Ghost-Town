#!/usr/bin/env python3
"""
Ornery-Kiwi — Media Intelligence Agent
Usage:
    python main.py [--watch] [--no-drive] [--process FILE]
"""

import argparse
import logging
import signal
import sys
import time
from pathlib import Path

from ornery_kiwi.config import WATCH_DIR, BASE_DIR, OUTPUT_DIR, PROCESSED_DIR
from ornery_kiwi.watcher import OrneryKiwiWatcher
from ornery_kiwi.pipeline import process_file


def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    fmt = "%(asctime)s  %(levelname)-8s  %(name)s — %(message)s"
    logging.basicConfig(level=level, format=fmt, datefmt="%H:%M:%S")
    # Quiet down noisy third-party loggers
    for noisy in ("httpx", "urllib3", "googleapiclient", "google"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def ensure_dirs():
    for d in [BASE_DIR, WATCH_DIR, OUTPUT_DIR, PROCESSED_DIR]:
        d.mkdir(parents=True, exist_ok=True)


def run_watch(drive_sync: bool, scan_existing: bool):
    watcher = OrneryKiwiWatcher(watch_dir=WATCH_DIR, drive_sync=drive_sync)
    watcher.start()

    if scan_existing:
        watcher.process_existing()

    stop_event = {"triggered": False}

    def _handle_signal(sig, frame):
        print("\nShutting down Ornery-Kiwi…")
        stop_event["triggered"] = True

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    while not stop_event["triggered"]:
        time.sleep(0.5)

    watcher.stop()


def run_single(file_path: str, drive_sync: bool):
    p = Path(file_path).expanduser().resolve()
    if not p.exists():
        print(f"Error: file not found: {p}", file=sys.stderr)
        sys.exit(1)
    result = process_file(p, drive_sync=drive_sync)
    print("\n--- Ornery-Kiwi Result ---")
    print(f"File:            {result['file']}")
    print(f"Type:            {result['type']}")
    print(f"Viability Score: {result['viability_score']}/10")
    print(f"Markdown:        {result['md_path']}")
    print(f"Word Doc:        {result['docx_path']}")
    if result["drive_urls"]:
        print("Drive URLs:")
        for name, url in result["drive_urls"].items():
            print(f"  {name}: {url}")
    if result["error"]:
        print(f"Error: {result['error']}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        prog="ornery-kiwi",
        description="Ornery-Kiwi: media intelligence agent",
    )
    parser.add_argument(
        "--watch", action="store_true",
        help=f"Watch {WATCH_DIR} for new media files (default mode)",
    )
    parser.add_argument(
        "--process", metavar="FILE",
        help="Process a single file and exit",
    )
    parser.add_argument(
        "--no-drive", action="store_true",
        help="Skip Google Drive sync",
    )
    parser.add_argument(
        "--scan-existing", action="store_true",
        help="Also process files already in the watch folder at startup",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Enable debug logging",
    )
    args = parser.parse_args()

    setup_logging(args.verbose)
    ensure_dirs()
    drive_sync = not args.no_drive

    if args.process:
        run_single(args.process, drive_sync)
    else:
        run_watch(drive_sync, args.scan_existing)


if __name__ == "__main__":
    main()
