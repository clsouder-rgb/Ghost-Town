"""Ingest functions for the Evidence Library."""

import uuid
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from . import db
from .models import EvidenceRecord, IngestRequest, SourceType, ConfidenceFlag, RecencyFlag

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return str(uuid.uuid4())


def ingest_from_request(req: IngestRequest) -> EvidenceRecord:
    """Ingest a manually-supplied evidence record via the API."""
    record = EvidenceRecord(
        id=_new_id(),
        date_added=_now_iso(),
        **req.model_dump(),
    )
    db.insert(record)
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
    Converts structured pipeline output directly into an evidence record
    without parsing the markdown report.
    """
    if not classification or classification.get("error"):
        logger.warning(f"[EvidenceLibrary] Skipping {source_file.name} — bad classification")
        return None

    score = classification.get("viability_score", 0)
    confidence = _score_to_confidence(score)

    tags = list(classification.get("recommended_tags", []))
    topics = classification.get("key_topics", [])
    category = classification.get("category", "")
    if category and category not in tags:
        tags.append(category)

    raw_parts = []
    if transcript:
        raw_parts.append(transcript)
    if image_text:
        raw_parts.append(image_text)
    if image_description:
        raw_parts.append(image_description)
    if classification.get("summary"):
        raw_parts.append(classification["summary"])

    source_path = str(md_path) if md_path else str(source_file)

    record = EvidenceRecord(
        id=_new_id(),
        title=classification.get("title") or source_file.stem,
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
        raw_content=" ".join(raw_parts),
        viability_score=score,
    )

    db.insert(record)
    logger.info(f"[EvidenceLibrary] Auto-ingested from pipeline: {record.title} (score={score})")
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
) -> EvidenceRecord:
    """Ingest a plain text document (PDF text dump, article, guideline, etc.)."""
    summary = content[:500].strip() + ("..." if len(content) > 500 else "")
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
        human_review_flag=True,   # manual ingests need human review
        tags=tags or [],
        raw_content=content,
    )
    db.insert(record)
    logger.info(f"[EvidenceLibrary] Ingested text doc: {title}")
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
