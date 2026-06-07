#!/usr/bin/env python3
"""
Evidence Library — batch file ingest CLI.

Scans a file or folder and ingests all supported documents into the
Evidence Library. Text is extracted automatically from PDF, DOCX, TXT, and MD.

Usage:
    # Ingest all files in a folder
    python ingest_files.py ~/Documents/ClinicalStudies/

    # Ingest a single file
    python ingest_files.py ~/Documents/study.pdf

    # Specify metadata
    python ingest_files.py ~/Documents/studies/ \\
        --type clinical_trial \\
        --tags "GLP-1,diabetes,RCT" \\
        --confidence high

    # Dry run — show what would be ingested without writing
    python ingest_files.py ~/Documents/studies/ --dry-run

    # Skip files already in the catalog (by source_path)
    python ingest_files.py ~/Documents/studies/ --skip-existing
"""

import argparse
import logging
import sys
from pathlib import Path

from evidence_library.extractors import SUPPORTED_EXTENSIONS as SUPPORTED

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def _is_supported(p: Path) -> bool:
    name = p.name.lower()
    return name.endswith(".tar.gz") or p.suffix.lower() in SUPPORTED


def collect_files(target: Path) -> list[Path]:
    if target.is_file():
        return [target] if _is_supported(target) else []
    return sorted(p for p in target.rglob("*") if p.is_file() and _is_supported(p))


def run(args):
    target = Path(args.path).expanduser().resolve()
    if not target.exists():
        print(f"ERROR: path not found: {target}", file=sys.stderr)
        sys.exit(1)

    files = collect_files(target)
    if not files:
        print(f"No supported files found at {target}")
        print(f"Supported formats: {', '.join(sorted(SUPPORTED))}")
        sys.exit(0)

    print(f"Found {len(files)} file(s) to ingest")
    if args.dry_run:
        print("DRY RUN — no records will be written\n")

    # Initialise Evidence Library DB
    if not args.dry_run:
        from ornery_kiwi.config import BASE_DIR
        from evidence_library import db
        db.init_db(BASE_DIR / "evidence.db")

    from evidence_library.extractors import extract_text, infer_metadata
    if not args.dry_run:
        from evidence_library.ingest import ingest_text_document
        from evidence_library.db import get_by_source_path

    tag_list = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else []

    results = {"ingested": 0, "skipped": 0, "failed": 0}

    for path in files:
        source_path_key = str(path)

        # Skip existing check
        if args.skip_existing and not args.dry_run:
            existing = get_by_source_path(source_path_key)
            if existing:
                print(f"  SKIP  {path.name}  (already in catalog: {existing.id[:8]}…)")
                results["skipped"] += 1
                continue

        # Extract text
        text, err = extract_text(path)
        if err:
            print(f"  FAIL  {path.name}  — {err}")
            results["failed"] += 1
            continue

        if not text.strip():
            print(f"  FAIL  {path.name}  — no text extracted")
            results["failed"] += 1
            continue

        meta = infer_metadata(text, path.name)
        char_count = len(text)

        if args.dry_run:
            print(f"  DRY   {path.name}")
            print(f"        title:   {meta['title']}")
            print(f"        chars:   {char_count:,}")
            print(f"        topic:   {meta.get('population_topic') or '(none detected)'}")
            results["ingested"] += 1
            continue

        try:
            record = ingest_text_document(
                title=meta["title"],
                content=text,
                source_type=args.type,
                source_path=source_path_key,
                tags=tag_list,
                citation=source_path_key,
                population_topic=meta.get("population_topic"),
                confidence_flag=args.confidence,
            )
            print(f"  OK    {path.name}")
            print(f"        id:      {record.id[:8]}…")
            print(f"        title:   {record.title}")
            print(f"        chars:   {char_count:,}  |  review: {record.human_review_flag}")
            results["ingested"] += 1
        except Exception as exc:
            print(f"  FAIL  {path.name}  — {exc}")
            results["failed"] += 1

    print()
    print(f"Done — ingested: {results['ingested']}  "
          f"skipped: {results['skipped']}  "
          f"failed: {results['failed']}")

    if not args.dry_run and results["ingested"] > 0:
        print()
        print("Verify in catalog:")
        print("  curl http://127.0.0.1:8000/evidence/catalog")
        print()
        print("Search by keyword:")
        print('  curl "http://127.0.0.1:8000/evidence/search?q=<keyword>"')


def main():
    parser = argparse.ArgumentParser(
        prog="ingest_files",
        description="Batch ingest files into the Evidence Library",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("path", help="File or folder to ingest")
    parser.add_argument(
        "--type", default="other",
        choices=["clinical_trial", "article", "guideline", "pdf", "report", "other"],
        help="Source type for all ingested files (default: other)",
    )
    parser.add_argument(
        "--tags", default="",
        help="Comma-separated tags applied to all files, e.g. 'GLP-1,diabetes,RCT'",
    )
    parser.add_argument(
        "--confidence", default="unknown",
        choices=["high", "medium", "low", "unknown"],
        help="Confidence flag for all ingested files (default: unknown)",
    )
    parser.add_argument(
        "--skip-existing", action="store_true",
        help="Skip files whose source_path is already in the catalog",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would be ingested without writing to the database",
    )
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
