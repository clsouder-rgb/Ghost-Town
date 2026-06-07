"""FastAPI routes for the Evidence Library — mounted at /evidence on the main app."""

import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form, Depends
import tempfile

from . import db
from .ingest import ingest_from_request, ingest_text_document
from .extractors import extract_text, infer_metadata, SUPPORTED_EXTENSIONS
from .models import (
    IngestRequest, IngestResponse,
    EvidencePacket, SearchResponse,
    CatalogEntry, ReviewPatch,
)
from .packet import to_packet, format_multi_packet_context
from ornery_kiwi.api.auth import check_write_token

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/evidence", tags=["evidence"])


# ── Write endpoints — authentication ──────────────────────────────────────────
#
# SECURITY: /evidence/ingest, /evidence/{id} (DELETE), and /evidence/{id}/review
# (PATCH) are write endpoints protected by optional API token.
#
# Token protection is ON when API_TOKEN env var is set (network mode).
# Token protection is OFF when API_TOKEN is empty (localhost-only mode).
#
# Binding is controlled by API_HOST env var:
#   API_HOST=127.0.0.1 (default) — localhost only, no token needed
#   API_HOST=0.0.0.0 — network accessible, API_TOKEN required for writes
#
# For network access, set in .env: API_TOKEN=your-secret-token-here
#
# ── Ingest ────────────────────────────────────────────────────────────────────

@router.post("/ingest", response_model=IngestResponse, status_code=201)
def ingest(body: IngestRequest, _: None = Depends(check_write_token)):
    """
    Manually ingest an evidence document (article, guideline, PDF metadata, etc.).
    WRITE OPERATION — requires API token if server is exposed to network.
    """
    record = ingest_from_request(body)
    return IngestResponse(id=record.id, title=record.title, message="Ingested successfully")


@router.post("/upload", response_model=IngestResponse, status_code=201)
async def upload_file(
    file: UploadFile = File(...),
    source_type: str = Form("other"),
    tags: str = Form(""),
    population_topic: str = Form(""),
    citation: str = Form(""),
    confidence_flag: str = Form("unknown"),
    _: None = Depends(check_write_token),
):
    """
    Upload a file (PDF, DOCX, TXT, MD) directly into the Evidence Library.
    Text is extracted automatically. Metadata can be supplied via form fields.

    WRITE OPERATION — requires API token if server is exposed to network.

    Example (curl):
        curl -X POST http://127.0.0.1:8000/evidence/upload \\
          -F "file=@/path/to/study.pdf" \\
          -F "source_type=clinical_trial" \\
          -F "tags=GLP-1,cardiovascular,RCT"
    """
    suffix = Path(file.filename).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{suffix}'. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}",
        )

    # Write upload to a temp file so extractors can read it normally
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = Path(tmp.name)

    try:
        text, err = extract_text(tmp_path)
        if err:
            raise HTTPException(status_code=422, detail=f"Extraction error: {err}")

        meta = infer_metadata(text, file.filename)
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]

        record = ingest_text_document(
            title=meta["title"],
            content=text,
            source_type=source_type,
            source_path=file.filename,
            tags=tag_list,
            citation=citation or file.filename,
            population_topic=population_topic or meta.get("population_topic"),
            confidence_flag=confidence_flag,
        )
    finally:
        tmp_path.unlink(missing_ok=True)

    return IngestResponse(
        id=record.id,
        title=record.title,
        message=f"Extracted {len(text):,} chars from {file.filename}",
    )


# ── Search ────────────────────────────────────────────────────────────────────

@router.get("/search", response_model=SearchResponse)
def search(
    q: Optional[str] = Query(None, description="Keyword search across title, summary, findings, content"),
    tags: Optional[str] = Query(None, description="Comma-separated tags to filter by"),
    source_type: Optional[str] = Query(None, description="Filter by source type"),
    human_review: bool = Query(False, description="Only return human-reviewed items"),
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """
    Deterministic keyword + tag search. Primary interface for SLIPSTREAM.
    Returns compact evidence packets — not full records.
    """
    tag_list = [t.strip() for t in tags.split(",")] if tags else None
    total, records = db.search(
        query=q,
        tags=tag_list,
        source_type=source_type,
        human_review_only=human_review,
        limit=limit,
        offset=offset,
    )
    packets = [to_packet(r) for r in records]
    return SearchResponse(query=q or "", total=total, packets=packets)


@router.get("/query", response_model=str)
def query_for_prompt(
    q: str = Query(..., description="Natural language or keyword query"),
    limit: int = Query(5, ge=1, le=20),
):
    """
    Returns a pre-formatted text block ready to inject into a SLIPSTREAM prompt.
    This is the endpoint SLIPSTREAM tools should call — smallest useful context.
    """
    _, records = db.search(query=q, limit=limit)
    packets = [to_packet(r) for r in records]
    return format_multi_packet_context(packets, query=q)


# ── Single record ─────────────────────────────────────────────────────────────

@router.get("/packet/{evidence_id}", response_model=EvidencePacket)
def get_packet(evidence_id: str):
    """Get a single compact evidence packet by ID."""
    record = db.get_by_id(evidence_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Evidence '{evidence_id}' not found")
    return to_packet(record)


@router.delete("/{evidence_id}", status_code=204)
def delete_evidence(evidence_id: str, _: None = Depends(check_write_token)):
    """
    Remove an evidence record.
    WRITE OPERATION — requires API token if server is exposed to network.
    """
    if not db.delete_by_id(evidence_id):
        raise HTTPException(status_code=404, detail=f"Evidence '{evidence_id}' not found")


@router.patch("/{evidence_id}/review", response_model=EvidencePacket)
def patch_review(evidence_id: str, body: ReviewPatch, _: None = Depends(check_write_token)):
    """
    Mark an item as human-reviewed and optionally update confidence/recency/limitations.
    WRITE OPERATION — requires API token if server is exposed to network.
    """
    updated = db.patch_review(
        evidence_id,
        human_review_flag=body.human_review_flag,
        confidence_flag=body.confidence_flag,
        recency_flag=body.recency_flag,
        limitations=body.limitations,
    )
    if not updated:
        raise HTTPException(status_code=404, detail=f"Evidence '{evidence_id}' not found")
    record = db.get_by_id(evidence_id)
    return to_packet(record)


# ── Catalog ───────────────────────────────────────────────────────────────────

@router.get("/catalog", response_model=dict)
def catalog(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List all evidence records — lightweight catalog view."""
    total, records = db.list_catalog(limit=limit, offset=offset)
    entries = [
        CatalogEntry(
            id=r.id,
            title=r.title,
            source_type=r.source_type,
            date_added=r.date_added[:10],
            tags=r.tags,
            confidence_flag=r.confidence_flag,
            human_review_flag=r.human_review_flag,
            viability_score=r.viability_score,
        )
        for r in records
    ]
    return {"total": total, "offset": offset, "entries": [e.model_dump() for e in entries]}
