from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


# ── Source types ──────────────────────────────────────────────────────────────

class SourceType:
    ORNERY_KIWI   = "ornery_kiwi"
    CLINICAL_TRIAL = "clinical_trial"
    ARTICLE       = "article"
    GUIDELINE     = "guideline"
    PDF           = "pdf"
    REPORT        = "report"
    OTHER         = "other"


class ConfidenceFlag:
    HIGH    = "high"
    MEDIUM  = "medium"
    LOW     = "low"
    UNKNOWN = "unknown"


class RecencyFlag:
    CURRENT = "current"
    DATED   = "dated"
    UNKNOWN = "unknown"


# ── Database row ──────────────────────────────────────────────────────────────

class EvidenceRecord(BaseModel):
    id: str
    title: str
    source_type: str
    source_path: Optional[str] = None
    date_added: str
    date_published: Optional[str] = None
    population_topic: Optional[str] = None
    summary: Optional[str] = None
    key_findings: Optional[str] = None
    limitations: Optional[str] = None
    citation: Optional[str] = None
    confidence_flag: str = ConfidenceFlag.UNKNOWN
    recency_flag: str = RecencyFlag.UNKNOWN
    human_review_flag: bool = False
    tags: list[str] = Field(default_factory=list)
    raw_content: Optional[str] = None
    viability_score: Optional[int] = None


# ── API request / response ────────────────────────────────────────────────────

class IngestRequest(BaseModel):
    title: str
    source_type: str = SourceType.OTHER
    source_path: Optional[str] = None
    date_published: Optional[str] = None
    population_topic: Optional[str] = None
    summary: Optional[str] = None
    key_findings: Optional[str] = None
    limitations: Optional[str] = None
    citation: Optional[str] = None
    confidence_flag: str = ConfidenceFlag.UNKNOWN
    recency_flag: str = RecencyFlag.UNKNOWN
    human_review_flag: bool = False
    tags: list[str] = Field(default_factory=list)
    raw_content: Optional[str] = None
    viability_score: Optional[int] = None


class IngestResponse(BaseModel):
    id: str
    title: str
    message: str


class EvidencePacket(BaseModel):
    """Compact payload returned to SLIPSTREAM — smallest useful unit."""
    id: str
    title: str
    source_type: str
    date: Optional[str]
    population_topic: Optional[str]
    key_findings: Optional[str]
    limitations: Optional[str]
    citation: Optional[str]
    confidence_flag: str
    recency_flag: str
    human_review_flag: bool
    tags: list[str]
    viability_score: Optional[int]


class SearchResponse(BaseModel):
    query: str
    total: int
    packets: list[EvidencePacket]


class CatalogEntry(BaseModel):
    id: str
    title: str
    source_type: str
    date_added: str
    tags: list[str]
    confidence_flag: str
    human_review_flag: bool
    viability_score: Optional[int]


class ReviewPatch(BaseModel):
    human_review_flag: bool
    confidence_flag: Optional[str] = None
    recency_flag: Optional[str] = None
    limitations: Optional[str] = None
