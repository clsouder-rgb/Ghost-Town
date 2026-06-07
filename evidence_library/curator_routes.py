"""FastAPI routes for Evidence Library curation — mounted at /curator."""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from . import db
from .models import CatalogEntry

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/curator", tags=["curator"])


@router.get("/browse")
def browse_records(
    reviewed: Optional[bool] = Query(None, description="Filter by review status (true/false/null for all)"),
    confidence: Optional[str] = Query(None, description="Filter by confidence flag"),
    tag: Optional[str] = Query(None, description="Filter by tag"),
    search: Optional[str] = Query(None, description="Search title/content"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """
    Browse and filter Evidence Library records.
    Returns catalog view with filtering options.
    """
    total, records = db.list_catalog(limit=limit + 1000, offset=offset)  # fetch more to filter

    # Apply filters
    filtered = records
    if reviewed is not None:
        filtered = [r for r in filtered if r.human_review_flag == reviewed]
    if confidence:
        filtered = [r for r in filtered if r.confidence_flag == confidence]
    if tag:
        filtered = [r for r in filtered if tag.lower() in (t.lower() for t in r.tags)]
    if search:
        search_lower = search.lower()
        filtered = [r for r in filtered if search_lower in r.title.lower() or search_lower in r.summary.lower()]

    # Limit results
    filtered = filtered[:limit]

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
        for r in filtered
    ]

    return {
        "total": total,
        "filtered": len(filtered),
        "offset": offset,
        "entries": [e.model_dump() for e in entries],
        "stats": {
            "reviewed": sum(1 for r in records if r.human_review_flag),
            "unreviewed": sum(1 for r in records if not r.human_review_flag),
            "high_confidence": sum(1 for r in records if r.confidence_flag == "high"),
            "tags": sorted(list(set(t for r in records for t in r.tags))),
        },
    }


@router.post("/review/{evidence_id}")
def mark_reviewed(
    evidence_id: str,
    human_review_flag: bool = Query(True),
    confidence_flag: Optional[str] = Query(None),
):
    """Mark a record as reviewed and optionally update confidence."""
    from .models import ReviewPatch

    patch = ReviewPatch(
        human_review_flag=human_review_flag,
        confidence_flag=confidence_flag,
        recency_flag=None,
        limitations=None,
    )

    updated = db.patch_review(
        evidence_id,
        human_review_flag=patch.human_review_flag,
        confidence_flag=patch.confidence_flag,
        recency_flag=patch.recency_flag,
        limitations=patch.limitations,
    )

    if not updated:
        raise HTTPException(status_code=404, detail=f"Evidence '{evidence_id}' not found")

    return {"id": evidence_id, "reviewed": human_review_flag, "confidence": confidence_flag}


@router.post("/tag/{evidence_id}")
def add_tags(evidence_id: str, tags: list[str] = Query(...)):
    """Add tags to a record."""
    record = db.get_by_id(evidence_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Evidence '{evidence_id}' not found")

    new_tags = sorted(list(set(record.tags + tags)))
    record = record.model_copy(update={"tags": new_tags})
    db.upsert(record)

    return {"id": evidence_id, "tags": new_tags}


@router.get("/stats")
def curator_stats():
    """Get overall Evidence Library statistics."""
    total, all_records = db.list_catalog(limit=10000)

    reviewed_count = sum(1 for r in all_records if r.human_review_flag)
    high_confidence_count = sum(1 for r in all_records if r.confidence_flag == "high")

    all_tags = {}
    for record in all_records:
        for tag in record.tags:
            all_tags[tag] = all_tags.get(tag, 0) + 1

    source_types = {}
    for record in all_records:
        st = record.source_type
        source_types[st] = source_types.get(st, 0) + 1

    return {
        "total_records": total,
        "reviewed": reviewed_count,
        "unreviewed": total - reviewed_count,
        "high_confidence": high_confidence_count,
        "review_percentage": round(100 * reviewed_count / max(1, total), 1),
        "top_tags": sorted(all_tags.items(), key=lambda x: x[1], reverse=True)[:20],
        "source_types": source_types,
    }
