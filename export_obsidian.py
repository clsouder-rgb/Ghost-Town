#!/usr/bin/env python3
"""
Export Evidence Library to Obsidian vault.

Usage:
    python export_obsidian.py ~/path/to/obsidian/vault
    python export_obsidian.py ~/path/to/obsidian/vault --reviewed-only
    python export_obsidian.py ~/path/to/obsidian/vault --min-confidence high
"""

import argparse
import logging
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        prog="export_obsidian",
        description="Export Evidence Library to Obsidian vault with bidirectional links",
    )
    parser.add_argument(
        "vault_dir",
        help="Path to Obsidian vault directory (e.g., ~/Documents/Obsidian/Evidence)",
    )
    parser.add_argument(
        "--reviewed-only",
        action="store_true",
        help="Only export records marked as human-reviewed",
    )
    parser.add_argument(
        "--min-confidence",
        choices=["high", "medium", "low", "unknown"],
        default=None,
        help="Only export records with this confidence level or higher",
    )
    args = parser.parse_args()

    vault_dir = Path(args.vault_dir).expanduser().resolve()
    if not vault_dir.parent.exists():
        print(f"ERROR: Parent directory not found: {vault_dir.parent}", file=sys.stderr)
        sys.exit(1)

    # Import here to ensure config is loaded
    from ornery_kiwi.config import BASE_DIR
    from evidence_library import db
    from evidence_library.obsidian_export import export_to_obsidian

    db.init_db(BASE_DIR / "evidence.db")

    print(f"Exporting Evidence Library to: {vault_dir}")
    print(f"  Reviewed only: {args.reviewed_only}")
    print(f"  Min confidence: {args.min_confidence or 'any'}")
    print()

    results = export_to_obsidian(
        vault_dir=vault_dir,
        db_module=db,
        include_unreviewed=not args.reviewed_only,
        min_confidence=args.min_confidence,
    )

    print()
    print(f"✓ Export complete:")
    print(f"  Exported: {results['exported']}")
    print(f"  Skipped:  {results['skipped']}")
    print(f"  Errors:   {results['errors']}")
    print()
    print(f"Obsidian vault ready at: {vault_dir}")
    print(f"Open Obsidian → Open vault folder → Browse 'studies' and 'tags'")


if __name__ == "__main__":
    main()
