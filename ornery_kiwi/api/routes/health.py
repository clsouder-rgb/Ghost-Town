from fastapi import APIRouter

from ornery_kiwi.config import BASE_DIR, WATCH_DIR
from ornery_kiwi.api.job_store import job_store
from ornery_kiwi.api.models import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["meta"])
async def health():
    return HealthResponse(
        status="ok",
        version="1.0.0",
        watch_dir=str(WATCH_DIR),
        active_jobs=job_store.count_active(),
        total_jobs=job_store.count_total(),
    )
