"""
Export Evidence Library records to Obsidian vault as markdown files with bidirectional links.
"""

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def export_to_obsidian(
    vault_dir: Path,
    db_module,
    include_unreviewed: bool = False,
    min_confidence: Optional[str] = None,
) -> dict:
    """
    Export Evidence Library to Obsidian vault structure.

    Args:
        vault_dir: Path to Obsidian vault (e.g., /Volumes/Obsidian/Evidence)
        db_module: evidence_library.db module
        include_unreviewed: Include records not marked as human_review_flag
        min_confidence: Only include records with this confidence or higher (high/medium/low/unknown)

    Returns:
        dict with counts: exported, skipped, errors
    """
    vault_dir = Path(vault_dir)
    vault_dir.mkdir(parents=True, exist_ok=True)

    studies_dir = vault_dir / "studies"
    studies_dir.mkdir(exist_ok=True)

    tags_dir = vault_dir / "tags"
    tags_dir.mkdir(exist_ok=True)

    results = {"exported": 0, "skipped": 0, "errors": 0}
    tag_index = {}  # tag -> list of study files
    all_records = []

    try:
        total, records = db_module.list_catalog(limit=10000)
        all_records = records
    except Exception as exc:
        logger.error(f"Failed to fetch records: {exc}")
        results["errors"] += 1
        return results

    # Export each record
    for record in all_records:
        # Filter by review status and confidence
        if not include_unreviewed and not record.human_review_flag:
            results["skipped"] += 1
            continue

        confidence_order = {"high": 0, "medium": 1, "low": 2, "unknown": 3}
        if min_confidence:
            record_confidence_rank = confidence_order.get(record.confidence_flag, 999)
            min_rank = confidence_order.get(min_confidence, 999)
            if record_confidence_rank > min_rank:
                results["skipped"] += 1
                continue

        try:
            # Create markdown file
            filename = f"{record.id[:8]}-{record.title[:40].replace('/', '-')}.md"
            filepath = studies_dir / filename

            # Build frontmatter
            tags_list = record.tags if isinstance(record.tags, list) else json.loads(record.tags or "[]")
            tags_str = "\n".join(f"  - {t}" for t in tags_list)

            md_content = f"""---
id: {record.id}
title: {record.title}
source_type: {record.source_type}
confidence: {record.confidence_flag}
reviewed: {record.human_review_flag}
date_added: {record.date_added}
citation: {record.citation}
tags:
{tags_str}
---

## {record.title}

**Source:** {record.source_type}
**Citation:** {record.citation}
**Confidence:** {record.confidence_flag} | **Reviewed:** {'Yes' if record.human_review_flag else 'No'}
**Date Added:** {record.date_added[:10]}

### Topic / Population
{record.population_topic or '(none identified)'}

### Summary
{record.summary[:500] if record.summary else '(no summary available)'}

### Content Preview
{record.content[:1500]}...

---

*For full content, query Evidence Library via API: `/evidence/packet/{record.id}`*
"""

            filepath.write_text(md_content, encoding="utf-8")
            results["exported"] += 1

            # Track tags
            for tag in tags_list:
                if tag not in tag_index:
                    tag_index[tag] = []
                tag_index[tag].append(filename)

            logger.debug(f"Exported: {filename}")

        except Exception as exc:
            logger.error(f"Failed to export record {record.id}: {exc}")
            results["errors"] += 1

    # Generate tag index files
    for tag, study_files in sorted(tag_index.items()):
        try:
            tag_file = tags_dir / f"{tag}.md"
            tag_links = "\n".join(f"  - [[{Path(f).stem}|{f}]]" for f in sorted(study_files))
            tag_content = f"""# {tag.replace('-', ' ').title()}

{len(study_files)} studies tagged with **#{tag}**

## Studies
{tag_links}
"""
            tag_file.write_text(tag_content, encoding="utf-8")
        except Exception as exc:
            logger.error(f"Failed to create tag file {tag}: {exc}")

    # Generate master index
    try:
        index_content = f"""# Evidence Library Index

Exported {results['exported']} clinical studies to Obsidian.

## Organization

- **[[studies/]]** — Individual study notes (click to browse)
- **[[tags/]]** — Tag-based index (explore by topic/drug/condition)

## Quick Links

### By Condition
{_generate_condition_links(tag_index)}

### By Drug
{_generate_drug_links(tag_index)}

### By Study Type
{_generate_type_links(tag_index)}

---

*Last exported: {Path(vault_dir).stat().st_mtime_ns}*
*Total studies: {results['exported']}*
"""
        index_file = vault_dir / "README.md"
        index_file.write_text(index_content, encoding="utf-8")
    except Exception as exc:
        logger.error(f"Failed to create index: {exc}")

    logger.info(
        f"Obsidian export complete: {results['exported']} exported, "
        f"{results['skipped']} skipped, {results['errors']} errors"
    )
    return results


def _generate_condition_links(tag_index: dict) -> str:
    """Generate markdown links for common conditions."""
    conditions = [t for t in tag_index.keys() if any(
        c in t for c in ["fibromyalgia", "pain", "crohn", "arthritis", "diabetes"]
    )]
    if not conditions:
        return "  (no conditions found)"
    return "\n".join(f"  - [[tags/{c}|{c.replace('-', ' ').title()}]]" for c in sorted(conditions))


def _generate_drug_links(tag_index: dict) -> str:
    """Generate markdown links for drugs."""
    drugs = [t for t in tag_index.keys() if any(
        d in t for d in ["naltrexone", "aspirin", "metformin", "lisinopril"]
    )]
    if not drugs:
        return "  (no drugs found)"
    return "\n".join(f"  - [[tags/{d}|{d.replace('-', ' ').title()}]]" for d in sorted(drugs))


def _generate_type_links(tag_index: dict) -> str:
    """Generate markdown links for study types."""
    types = [t for t in tag_index.keys() if any(
        st in t for st in ["rct", "meta-analysis", "case-study", "cohort"]
    )]
    if not types:
        return "  (no study types found)"
    return "\n".join(f"  - [[tags/{t}|{t.replace('-', ' ').title()}]]" for t in sorted(types))
