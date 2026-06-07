"""Ingest functions for the Evidence Library."""

import hashlib
import uuid
import logging
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional

from . import db
from .models import EvidenceRecord, IngestRequest, SourceType, ConfidenceFlag, RecencyFlag
from .auto_tagger import extract_auto_tags, extract_citations

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return str(uuid.uuid4())


def _content_hash(text: str) -> str:
    """SHA-256 of normalised content — catches exact duplicates regardless of filename."""
    normalised = " ".join(text.lower().split())
    return hashlib.sha256(normalised.encode()).hexdigest()


def _find_similar_title(title: str, threshold: float) -> Optional[tuple[str, str, float]]:
    """
    Check existing record titles for near-duplicates.
    Returns (id, existing_title, similarity_ratio) if a match above threshold is found,
    otherwise None.
    """
    title_lower = title.lower()
    for record_id, existing_title in db.get_all_titles():
        ratio = SequenceMatcher(None, title_lower, existing_title.lower()).ratio()
        if ratio >= threshold:
            return record_id, existing_title, ratio
    return None


def _governance_check(
    title: str,
    content: str,
    score: Optional[int],
    min_score: int,
    title_threshold: float,
) -> Optional[str]:
    """
    Run all governance checks before ingest. Returns a skip-reason string if the
    record should be rejected, or None if it passes.
    """
    # 1. Viability score floor (only applies when score is provided)
    if score is not None and score < min_score:
        return f"viability score {score} below minimum {min_score}"

    # 2. Exact content hash duplicate
    if content:
        h = _content_hash(content)
        existing = db.get_by_content_hash(h)
        if existing:
            return f"exact duplicate of '{existing.title}' (id={existing.id[:8]})"

    # 3. Near-duplicate title
    match = _find_similar_title(title, title_threshold)
    if match:
        eid, etitle, ratio = match
        return f"title {ratio:.0%} similar to existing '{etitle}' (id={eid[:8]})"

    return None


def ingest_from_request(req: IngestRequest) -> EvidenceRecord:
    """Ingest a manually-supplied evidence record via the API."""
    record = EvidenceRecord(
        id=_new_id(),
        date_added=_now_iso(),
        content_hash=_content_hash(req.raw_content or req.title),
        **req.model_dump(),
    )
    db.upsert(record)
    logger.info(f"[EvidenceLibrary] Ingested: {record.title} ({record.id})")
    return record


def ingest_pipeline_result(
    source_file: Path,
    file_type: str,
    classification: dict,
    transcript: str = "",
    image_text: str = "",
    image_description: str = "",
    md_path: Optional[Path] = None,
    docx_path: Optional[Path] = None,
) -> Optional[EvidenceRecord]:
    """
    Called automatically by Ornery-Kiwi pipeline after processing a file.
    Applies full governance checks before writing to the Evidence Library.
    """
    if not classification or classification.get("error"):
        logger.warning(f"[EvidenceLibrary] Skipping {source_file.name} — bad classification")
        return None

    score = classification.get("viability_score", 0)
    title = classification.get("title") or source_file.stem

    raw_parts = [p for p in [transcript, image_text, image_description,
                               classification.get("summary")] if p]
    raw_content = " ".join(raw_parts)

    # ── Governance checks ──────────────────────────────────────────────────────
    try:
        from ornery_kiwi.config import EVIDENCE_MIN_SCORE, EVIDENCE_TITLE_SIMILARITY
    except ImportError:
        EVIDENCE_MIN_SCORE, EVIDENCE_TITLE_SIMILARITY = 4, 0.85

    skip_reason = _governance_check(title, raw_content, score, EVIDENCE_MIN_SCORE, EVIDENCE_TITLE_SIMILARITY)
    if skip_reason:
        logger.info(f"[EvidenceLibrary] Skipped '{title}': {skip_reason}")
        return None

    # ── Build record ───────────────────────────────────────────────────────────
    confidence = _score_to_confidence(score)
    tags = list(classification.get("recommended_tags", []))
    category = classification.get("category", "")
    if category and category not in tags:
        tags.append(category)
    topics = classification.get("key_topics", [])
    source_path = str(md_path) if md_path else str(source_file)

    record = EvidenceRecord(
        id=_new_id(),
        title=title,
        source_type=SourceType.ORNERY_KIWI,
        source_path=source_path,
        date_added=_now_iso(),
        population_topic=", ".join(topics) if topics else classification.get("target_audience"),
        summary=classification.get("summary"),
        key_findings=classification.get("viability_reasoning"),
        limitations=_build_limitations(classification),
        citation=str(source_file),
        confidence_flag=confidence,
        recency_flag=RecencyFlag.CURRENT,
        human_review_flag=False,
        tags=tags,
        raw_content=raw_content,
        viability_score=score,
        content_hash=_content_hash(raw_content) if raw_content else None,
    )

    db.upsert(record)
    logger.info(f"[EvidenceLibrary] Auto-ingested: {record.title} (score={score})")
    return record


def ingest_text_document(
    title: str,
    content: str,
    source_type: str = SourceType.OTHER,
    source_path: Optional[str] = None,
    tags: Optional[list[str]] = None,
    citation: Optional[str] = None,
    date_published: Optional[str] = None,
    population_topic: Optional[str] = None,
    confidence_flag: str = ConfidenceFlag.UNKNOWN,
) -> Optional[EvidenceRecord]:
    """Ingest a plain text document (PDF text dump, article, guideline, etc.)."""
    try:
        from ornery_kiwi.config import EVIDENCE_TITLE_SIMILARITY
    except ImportError:
        EVIDENCE_TITLE_SIMILARITY = 0.85

    # ── Governance checks ──────────────────────────────────────────────────────
    # No score floor for manual text documents — user dropped them intentionally.
    # Still block exact and near-duplicate content.
    skip_reason = _governance_check(title, content, None, 0, EVIDENCE_TITLE_SIMILARITY)
    if skip_reason:
        logger.info(f"[EvidenceLibrary] Skipped '{title}': {skip_reason}")
        return None

    summary = content[:500].strip() + ("..." if len(content) > 500 else "")

    auto_tags = extract_auto_tags(content, filename=str(source_path or title))
    merged_tags = sorted(list(set(tags or []) | set(auto_tags)))

    record = EvidenceRecord(
        id=_new_id(),
        title=title,
        source_type=source_type,
        source_path=source_path,
        date_added=_now_iso(),
        date_published=date_published,
        population_topic=population_topic,
        summary=summary,
        citation=citation or source_path,
        confidence_flag=confidence_flag,
        recency_flag=RecencyFlag.UNKNOWN,
        human_review_flag=True,
        tags=merged_tags,
        raw_content=content,
        content_hash=_content_hash(content),
    )
    db.upsert(record)
    logger.info(f"[EvidenceLibrary] Ingested text doc: {title} with {len(merged_tags)} tags")
    return record


# ── helpers ───────────────────────────────────────────────────────────────────

def _score_to_confidence(score: int) -> str:
    if score >= 7:
        return ConfidenceFlag.HIGH
    elif score >= 4:
        return ConfidenceFlag.MEDIUM
    return ConfidenceFlag.LOW


def _build_limitations(classification: dict) -> Optional[str]:
    flags = classification.get("content_flags", [])
    if not flags:
        return None
    return "Content flags: " + "; ".join(flags)
