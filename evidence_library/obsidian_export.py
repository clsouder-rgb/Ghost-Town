"""
Export Evidence Library records to Obsidian vault as markdown files.

File naming:  YYYY-MM-DD - Title of Record.md
Tag strategy: YAML frontmatter tags (Obsidian tag pane) +
              inline #hashtags + [[wikilinks]] to tag index pages
"""

import json
import logging
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_CONFIDENCE_EMOJI = {"high": "🟢", "medium": "🟡", "low": "🔴", "unknown": "⚪"}
_DOMAIN_LABELS = {
    "clinical": "🏥 Clinical",
    "tech": "💻 Technology",
    "fitness": "💪 Fitness",
    "recipe": "🍽️ Recipe",
    "tutorial": "📖 Tutorial",
    "quote": "💬 Quote / Philosophy",
    "academic": "🎓 Academic",
    "business": "📊 Business",
    "science": "🔬 Science",
    "general": "📄 General",
}


def _safe_filename(title: str, date: str) -> str:
    """Convert title to a safe, readable Obsidian filename."""
    date_prefix = date[:10] if date else "0000-00-00"
    clean = re.sub(r'[\\/:*?"<>|]', "", title)   # strip illegal chars
    clean = re.sub(r"\s+", " ", clean).strip()
    clean = clean[:80].rstrip(". ")               # max 80 chars, no trailing dots
    return f"{date_prefix} - {clean}.md"


def _tag_links(tags: list[str]) -> str:
    """Render tags as both Obsidian wikilinks and hashtags."""
    if not tags:
        return "(none)"
    parts = []
    for tag in sorted(tags):
        label = tag.replace("-", " ").title()
        parts.append(f"[[tags/{tag}|{label}]] #{tag}")
    return "  •  ".join(parts)


def _domain_from_tags(tags: list[str]) -> str:
    for tag in tags:
        if tag.startswith("domain-"):
            domain = tag.replace("domain-", "")
            return _DOMAIN_LABELS.get(domain, domain.title())
    return _DOMAIN_LABELS["general"]


def _render_record(record) -> str:
    """Render a single EvidenceRecord as Obsidian markdown."""
    tags_list = record.tags if isinstance(record.tags, list) else json.loads(record.tags or "[]")

    # YAML frontmatter — Obsidian reads these for tag pane + search
    frontmatter_tags = "\n".join(f"  - {t}" for t in sorted(tags_list))
    domain = _domain_from_tags(tags_list)
    confidence_badge = _CONFIDENCE_EMOJI.get(record.confidence_flag, "⚪")
    date_display = record.date_added[:10] if record.date_added else ""

    summary = (record.summary or "").strip() or "(no summary available)"
    key_findings = (record.key_findings or "").strip() or "(none recorded)"
    limitations = (record.limitations or "").strip() or "(none recorded)"
    population = (record.population_topic or "").strip() or "(not specified)"
    raw = (record.raw_content or "").strip()
    preview = (raw[:1200] + "...") if len(raw) > 1200 else raw

    tag_link_line = _tag_links(tags_list)

    return f"""---
id: {record.id}
title: "{record.title.replace('"', "'")}"
source_type: {record.source_type}
confidence: {record.confidence_flag}
viability_score: {record.viability_score or 0}
reviewed: {str(record.human_review_flag).lower()}
date_added: {date_display}
citation: "{(record.citation or '').replace('"', "'")}"
tags:
{frontmatter_tags}
---

# {record.title}

> {confidence_badge} **{record.confidence_flag.upper()}** confidence  |  Domain: **{domain}**  |  Score: **{record.viability_score or 0}/10**  |  Added: {date_display}

---

## Summary
{summary}

## Key Findings
{key_findings}

## Limitations
{limitations}

## Topic / Population
{population}

---

## Tags & Connections

{tag_link_line}

---

## Content Preview

{preview}

---

*Source: `{record.source_type}` | Citation: `{record.citation or 'n/a'}`*
*Evidence Library ID: `{record.id}`*
"""


def export_single_record(record, vault_dir: Path) -> Optional[Path]:
    """
    Write (or overwrite) the Obsidian file for a single record.
    Called automatically after each ingest when OBSIDIAN_VAULT is set.
    Returns the path written, or None on error.
    """
    vault_dir = Path(vault_dir)
    studies_dir = vault_dir / "studies"
    studies_dir.mkdir(parents=True, exist_ok=True)

    try:
        filename = _safe_filename(record.title, record.date_added)
        filepath = studies_dir / filename
        filepath.write_text(_render_record(record), encoding="utf-8")
        _update_tag_pages(record, vault_dir)
        _update_index(vault_dir)
        logger.info(f"[Obsidian] Written: {filename}")
        return filepath
    except Exception as exc:
        logger.warning(f"[Obsidian] Failed to write {record.title[:40]}: {exc}")
        return None


def export_to_obsidian(
    vault_dir: Path,
    db_module,
    include_unreviewed: bool = True,
    min_confidence: Optional[str] = None,
) -> dict:
    """Full re-export of all matching Evidence Library records to Obsidian vault."""
    vault_dir = Path(vault_dir)
    (vault_dir / "studies").mkdir(parents=True, exist_ok=True)
    (vault_dir / "tags").mkdir(parents=True, exist_ok=True)

    results = {"exported": 0, "skipped": 0, "errors": 0}
    confidence_order = {"high": 0, "medium": 1, "low": 2, "unknown": 3}
    tag_index: dict[str, list[str]] = {}

    try:
        _, records = db_module.list_catalog(limit=10000)
    except Exception as exc:
        logger.error(f"Failed to fetch records: {exc}")
        results["errors"] += 1
        return results

    for record in records:
        if not include_unreviewed and not record.human_review_flag:
            results["skipped"] += 1
            continue
        if min_confidence:
            if confidence_order.get(record.confidence_flag, 9) > confidence_order.get(min_confidence, 9):
                results["skipped"] += 1
                continue

        try:
            filename = _safe_filename(record.title, record.date_added)
            filepath = vault_dir / "studies" / filename
            filepath.write_text(_render_record(record), encoding="utf-8")
            results["exported"] += 1

            tags_list = record.tags if isinstance(record.tags, list) else json.loads(record.tags or "[]")
            for tag in tags_list:
                tag_index.setdefault(tag, []).append(filename)
        except Exception as exc:
            logger.error(f"Failed to export {record.id}: {exc}")
            results["errors"] += 1

    _write_tag_pages(tag_index, vault_dir)
    _write_index(records, results["exported"], vault_dir)

    logger.info(
        f"[Obsidian] Export complete: {results['exported']} exported, "
        f"{results['skipped']} skipped, {results['errors']} errors"
    )
    return results


# ── Tag pages ─────────────────────────────────────────────────────────────────

def _write_tag_pages(tag_index: dict[str, list[str]], vault_dir: Path):
    tags_dir = vault_dir / "tags"
    tags_dir.mkdir(exist_ok=True)
    for tag, filenames in sorted(tag_index.items()):
        _write_single_tag_page(tag, filenames, tags_dir)


def _write_single_tag_page(tag: str, filenames: list[str], tags_dir: Path):
    label = tag.replace("-", " ").title()
    links = "\n".join(
        f"- [[{Path(f).stem}]]" for f in sorted(filenames)
    )
    content = f"""# #{tag}

**{label}** — {len(filenames)} record{'s' if len(filenames) != 1 else ''}

## Records

{links}
"""
    (tags_dir / f"{tag}.md").write_text(content, encoding="utf-8")


def _update_tag_pages(record, vault_dir: Path):
    """Update only the tag pages touched by a single record."""
    tags_dir = vault_dir / "tags"
    tags_dir.mkdir(exist_ok=True)
    tags_list = record.tags if isinstance(record.tags, list) else json.loads(record.tags or "[]")
    filename = _safe_filename(record.title, record.date_added)
    stem = Path(filename).stem

    for tag in tags_list:
        tag_file = tags_dir / f"{tag}.md"
        if tag_file.exists():
            existing = tag_file.read_text(encoding="utf-8")
            if stem not in existing:
                tag_file.write_text(existing.rstrip() + f"\n- [[{stem}]]\n", encoding="utf-8")
        else:
            _write_single_tag_page(tag, [filename], tags_dir)


# ── Master index ──────────────────────────────────────────────────────────────

def _write_index(records, exported_count: int, vault_dir: Path):
    from datetime import datetime
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Group by domain
    domain_groups: dict[str, list] = {}
    for r in records:
        tags_list = r.tags if isinstance(r.tags, list) else json.loads(r.tags or "[]")
        domain = next((t.replace("domain-", "") for t in tags_list if t.startswith("domain-")), "general")
        domain_groups.setdefault(domain, []).append(r)

    domain_sections = []
    for domain in sorted(domain_groups):
        label = _DOMAIN_LABELS.get(domain, domain.title())
        items = domain_groups[domain]
        links = "\n".join(
            f"- [[{Path(_safe_filename(r.title, r.date_added)).stem}|{r.title[:60]}]]"
            for r in sorted(items, key=lambda x: x.date_added, reverse=True)[:10]
        )
        domain_sections.append(f"### {label}\n{links}")

    sections = "\n\n".join(domain_sections)

    content = f"""# Evidence Library

**{exported_count} records** across {len(domain_groups)} domains  |  Last updated: {now}

## Browse by Domain

{sections}

---

## Browse All Tags

[[tags/]] — open the tags folder to explore all connected topics

---

*Powered by Ornery-Kiwi + Evidence Library*
"""
    (vault_dir / "README.md").write_text(content, encoding="utf-8")


def _update_index(vault_dir: Path):
    """Lightweight index refresh — just updates the timestamp line."""
    index_file = vault_dir / "README.md"
    if not index_file.exists():
        return
    from datetime import datetime
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    text = index_file.read_text(encoding="utf-8")
    text = re.sub(r"Last updated: [\d\- :]+", f"Last updated: {now}", text)
    index_file.write_text(text, encoding="utf-8")
