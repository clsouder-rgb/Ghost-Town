from datetime import datetime
from typing import Optional
from pydantic import BaseModel, model_validator


class IngestRequest(BaseModel):
    url: Optional[str] = None
    file_path: Optional[str] = None

    @model_validator(mode="after")
    def _require_one(self) -> "IngestRequest":
        if not self.url and not self.file_path:
            raise ValueError("Provide either 'url' or 'file_path'")
        return self


class IngestResponse(BaseModel):
    job_id: str
    status: str
    message: Optional[str] = None


class JobResult(BaseModel):
    file: Optional[str] = None
    type: Optional[str] = None
    md_path: Optional[str] = None
    docx_path: Optional[str] = None
    viability_score: Optional[int] = None
    drive_urls: Optional[dict[str, str]] = None


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    source: str
    created_at: datetime
    updated_at: datetime
    result: Optional[JobResult] = None
    error: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    version: str
    watch_dir: str
    active_jobs: int
    total_jobs: int
