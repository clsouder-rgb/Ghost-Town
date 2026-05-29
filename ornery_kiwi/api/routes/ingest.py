import asyncio
import logging
import shutil
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException

from ornery_kiwi.api.job_store import job_store, JobStatus
from ornery_kiwi.api.models import IngestRequest, IngestResponse, JobResult, JobStatusResponse
from ornery_kiwi.config import WATCH_DIR
from ornery_kiwi.pipeline import process_file

logger = logging.getLogger(__name__)
router = APIRouter(tags=["ingest"])

_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="ingest-worker")


@router.post("/ingest", response_model=IngestResponse, status_code=202)
async def ingest(body: IngestRequest):
    """Accept a URL or local file path and queue it for processing."""
    source = body.url or body.file_path
    job = job_store.create(source)

    loop = asyncio.get_running_loop()
    loop.run_in_executor(_executor, _run_job, job.job_id, body.url, body.file_path)

    return IngestResponse(
        job_id=job.job_id,
        status=job.status,
        message=f"Job queued. Poll /ingest/status/{job.job_id} for updates.",
    )


@router.get("/ingest/status/{job_id}", response_model=JobStatusResponse)
async def get_status(job_id: str):
    """Poll the status of a queued or completed ingestion job."""
    job = job_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    result = None
    if job.result:
        result = JobResult(
            file=job.result.get("file"),
            type=job.result.get("type"),
            md_path=job.result.get("md_path"),
            docx_path=job.result.get("docx_path"),
            viability_score=job.result.get("viability_score"),
            drive_urls=job.result.get("drive_urls") or {},
        )

    return JobStatusResponse(
        job_id=job.job_id,
        status=job.status,
        source=job.source,
        created_at=job.created_at,
        updated_at=job.updated_at,
        result=result,
        error=job.error,
    )


# ── Background worker ────────────────────────────────────────────────────────

def _run_job(job_id: str, url: str | None, file_path: str | None):
    job_store.update(job_id, JobStatus.PROCESSING)
    try:
        if url:
            local_path = _download(url)
        else:
            local_path = Path(file_path).expanduser().resolve()
            if not local_path.exists():
                raise FileNotFoundError(f"File not found: {local_path}")

        result = process_file(local_path, drive_sync=True)

        if result.get("error"):
            job_store.update(job_id, JobStatus.FAILED, error=result["error"])
        else:
            job_store.update(job_id, JobStatus.COMPLETE, result=result)

    except Exception as exc:
        logger.error(f"Job {job_id} failed: {exc}", exc_info=True)
        job_store.update(job_id, JobStatus.FAILED, error=str(exc))


def _download(url: str) -> Path:
    """Download URL to watch dir and return its local path."""
    WATCH_DIR.mkdir(parents=True, exist_ok=True)
    parsed = urlparse(url)
    filename = Path(parsed.path).name or "download"
    dest = WATCH_DIR / filename

    logger.info(f"Downloading {url} → {dest}")
    with urllib.request.urlopen(url, timeout=120) as resp:
        with open(dest, "wb") as f:
            shutil.copyfileobj(resp, f)

    return dest
