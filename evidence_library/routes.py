"""FastAPI routes for the Evidence Library — mounted at /evidence on the main app."""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from . import db
from .ingest import ingest_from_request
from .models import (
    IngestRequest, IngestResponse,
    EvidencePacket, SearchResponse,
    CatalogEntry, ReviewPatch,
)
from .packet import to_packet, format_multi_packet_context

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/evidence", tags=["evidence"])


# ── Write endpoints — localhost-only protection notice ────────────────────────
#
# SECURITY: /evidence/ingest, /evidence/{id} (DELETE), and /evidence/{id}/review
# (PATCH) are write endpoints with NO authentication.
#
# They are safe ONLY while the server binds to 127.0.0.1 (localhost).
# Do NOT expose this service on 0.0.0.0 or any external network interface
# without adding authentication first (e.g. API key header, Bearer token).
#
# Current binding is set in serve.py --host argument and the launchd plist
# (127.0.0.1 only). Verify with: lsof -i :8000
#
# ── Ingest ────────────────────────────────────────────────────────────────────

@router.post("/ingest", response_model=IngestResponse, status_code=201)
def ingest(body: IngestRequest):
    """
    Manually ingest an evidence document (article, guideline, PDF metadata, etc.).
    WRITE OPERATION — localhost-only, no authentication. See security notice above.
    """
    record = ingest_from_request(body)
    return IngestResponse(id=record.id, title=record.title, message="Ingested successfully")


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
def delete_evidence(evidence_id: str):
    """
    Remove an evidence record.
    WRITE OPERATION — localhost-only, no authentication. See security notice above.
    """
    if not db.delete_by_id(evidence_id):
        raise HTTPException(status_code=404, detail=f"Evidence '{evidence_id}' not found")


@router.patch("/{evidence_id}/review", response_model=EvidencePacket)
def patch_review(evidence_id: str, body: ReviewPatch):
    """
    Mark an item as human-reviewed and optionally update confidence/recency/limitations.
    WRITE OPERATION — localhost-only, no authentication. See security notice above.
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
