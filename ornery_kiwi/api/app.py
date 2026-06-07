from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes.health import router as health_router
from .routes.ingest import router as ingest_router
from evidence_library.routes import router as evidence_router
from evidence_library import db as evidence_db
from ornery_kiwi.config import BASE_DIR

# Initialise Evidence Library SQLite DB at startup
evidence_db.init_db(BASE_DIR / "evidence.db")

app = FastAPI(
    title="Ornery-Kiwi + Evidence Library",
    description="Media intelligence agent with local evidence store for SLIPSTREAM",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten before production
    allow_methods=["GET", "POST", "DELETE", "PATCH"],
    allow_headers=["Content-Type", "Authorization"],
)

app.include_router(health_router)
app.include_router(ingest_router)
app.include_router(evidence_router)
