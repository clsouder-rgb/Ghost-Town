import threading
import uuid
from datetime import datetime, timezone
from typing import Optional


class JobStatus:
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETE = "complete"
    FAILED = "failed"


class Job:
    def __init__(self, job_id: str, source: str):
        self.job_id = job_id
        self.source = source
        self.status = JobStatus.QUEUED
        self.result: Optional[dict] = None
        self.error: Optional[str] = None
        self.created_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "status": self.status,
            "source": self.source,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "result": self.result,
            "error": self.error,
        }


class JobStore:
    def __init__(self):
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def create(self, source: str) -> Job:
        job = Job(str(uuid.uuid4()), source)
        with self._lock:
            self._jobs[job.job_id] = job
        return job

    def get(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)

    def update(self, job_id: str, status: str, result: dict | None = None, error: str | None = None):
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            job.status = status
            job.updated_at = datetime.now(timezone.utc)
            if result is not None:
                job.result = result
            if error is not None:
                job.error = error

    def count_active(self) -> int:
        with self._lock:
            return sum(
                1 for j in self._jobs.values()
                if j.status in (JobStatus.QUEUED, JobStatus.PROCESSING)
            )

    def count_total(self) -> int:
        with self._lock:
            return len(self._jobs)


# Module-level singleton shared across routes
job_store = JobStore()
