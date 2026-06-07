"""SQLite layer for the Evidence Library."""

import json
import sqlite3
import threading
from pathlib import Path
from typing import Optional

from .models import EvidenceRecord

_DB_PATH: Optional[Path] = None
_local = threading.local()


def init_db(db_path: Path):
    """Call once at startup with the desired database path."""
    global _DB_PATH
    _DB_PATH = Path(db_path)
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    _create_tables(_connect())


def _connect() -> sqlite3.Connection:
    """Return a thread-local connection."""
    if not hasattr(_local, "conn") or _local.conn is None:
        if _DB_PATH is None:
            raise RuntimeError("Call init_db() before using the Evidence Library")
        conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        _local.conn = conn
    return _local.conn


def _create_tables(conn: sqlite3.Connection):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS evidence (
            id                TEXT PRIMARY KEY,
            title             TEXT NOT NULL,
            source_type       TEXT NOT NULL DEFAULT 'other',
            source_path       TEXT,
            date_added        TEXT NOT NULL,
            date_published    TEXT,
            population_topic  TEXT,
            summary           TEXT,
            key_findings      TEXT,
            limitations       TEXT,
            citation          TEXT,
            confidence_flag   TEXT NOT NULL DEFAULT 'unknown',
            recency_flag      TEXT NOT NULL DEFAULT 'unknown',
            human_review_flag INTEGER NOT NULL DEFAULT 0,
            tags              TEXT NOT NULL DEFAULT '[]',
            raw_content       TEXT,
            viability_score   INTEGER
        );

        CREATE INDEX IF NOT EXISTS idx_evidence_source_type
            ON evidence(source_type);
        CREATE INDEX IF NOT EXISTS idx_evidence_date_added
            ON evidence(date_added);
        CREATE INDEX IF NOT EXISTS idx_evidence_confidence
            ON evidence(confidence_flag);
        CREATE INDEX IF NOT EXISTS idx_evidence_human_review
            ON evidence(human_review_flag);
    """)
    conn.commit()


# ── CRUD ──────────────────────────────────────────────────────────────────────

def insert(record: EvidenceRecord):
    conn = _connect()
    conn.execute(
        """
        INSERT OR REPLACE INTO evidence
            (id, title, source_type, source_path, date_added, date_published,
             population_topic, summary, key_findings, limitations, citation,
             confidence_flag, recency_flag, human_review_flag, tags,
             raw_content, viability_score)
        VALUES
            (:id, :title, :source_type, :source_path, :date_added, :date_published,
             :population_topic, :summary, :key_findings, :limitations, :citation,
             :confidence_flag, :recency_flag, :human_review_flag, :tags,
             :raw_content, :viability_score)
        """,
        {
            **record.model_dump(),
            "tags": json.dumps(record.tags),
            "human_review_flag": int(record.human_review_flag),
        },
    )
    conn.commit()


def get_by_source_path(source_path: str) -> Optional[EvidenceRecord]:
    """Look up an existing record by source_path. Used for duplicate prevention."""
    conn = _connect()
    row = conn.execute(
        "SELECT * FROM evidence WHERE source_path = ? LIMIT 1", (source_path,)
    ).fetchone()
    return _row_to_record(row) if row else None


def upsert(record: EvidenceRecord):
    """
    Insert or update by source_path.

    - If source_path is set and a record with that path already exists:
        preserve the original id and date_added, update all other fields.
    - Otherwise: insert as a new record.

    This prevents duplicate catalog entries when the same source file
    is re-processed (e.g. dropped into the watch folder twice).
    """
    if record.source_path:
        existing = get_by_source_path(record.source_path)
        if existing:
            # Preserve original identity and first-seen date
            record = record.model_copy(update={
                "id": existing.id,
                "date_added": existing.date_added,
            })
    insert(record)


def get_by_id(evidence_id: str) -> Optional[EvidenceRecord]:
    conn = _connect()
    row = conn.execute(
        "SELECT * FROM evidence WHERE id = ?", (evidence_id,)
    ).fetchone()
    return _row_to_record(row) if row else None


def delete_by_id(evidence_id: str) -> bool:
    conn = _connect()
    cur = conn.execute("DELETE FROM evidence WHERE id = ?", (evidence_id,))
    conn.commit()
    return cur.rowcount > 0


def patch_review(
    evidence_id: str,
    human_review_flag: bool,
    confidence_flag: Optional[str] = None,
    recency_flag: Optional[str] = None,
    limitations: Optional[str] = None,
) -> bool:
    sets = ["human_review_flag = ?"]
    params: list = [int(human_review_flag)]

    if confidence_flag is not None:
        sets.append("confidence_flag = ?")
        params.append(confidence_flag)
    if recency_flag is not None:
        sets.append("recency_flag = ?")
        params.append(recency_flag)
    if limitations is not None:
        sets.append("limitations = ?")
        params.append(limitations)

    params.append(evidence_id)
    conn = _connect()
    cur = conn.execute(
        f"UPDATE evidence SET {', '.join(sets)} WHERE id = ?", params
    )
    conn.commit()
    return cur.rowcount > 0


def search(
    query: Optional[str] = None,
    tags: Optional[list[str]] = None,
    source_type: Optional[str] = None,
    human_review_only: bool = False,
    limit: int = 20,
    offset: int = 0,
) -> tuple[int, list[EvidenceRecord]]:
    """Deterministic keyword + tag search. Returns (total_count, records)."""
    where_clauses = []
    params: list = []

    if query:
        terms = query.strip().split()
        for term in terms:
            where_clauses.append(
                "(title LIKE ? OR summary LIKE ? OR key_findings LIKE ? "
                "OR population_topic LIKE ? OR raw_content LIKE ? OR tags LIKE ?)"
            )
            like = f"%{term}%"
            params.extend([like, like, like, like, like, like])

    if tags:
        for tag in tags:
            where_clauses.append("tags LIKE ?")
            params.append(f'%"{tag}"%')

    if source_type:
        where_clauses.append("source_type = ?")
        params.append(source_type)

    if human_review_only:
        where_clauses.append("human_review_flag = 1")

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    conn = _connect()
    total = conn.execute(
        f"SELECT COUNT(*) FROM evidence {where_sql}", params
    ).fetchone()[0]

    rows = conn.execute(
        f"SELECT * FROM evidence {where_sql} ORDER BY date_added DESC LIMIT ? OFFSET ?",
        params + [limit, offset],
    ).fetchall()

    return total, [_row_to_record(r) for r in rows]


def list_catalog(limit: int = 100, offset: int = 0) -> tuple[int, list[EvidenceRecord]]:
    conn = _connect()
    total = conn.execute("SELECT COUNT(*) FROM evidence").fetchone()[0]
    rows = conn.execute(
        "SELECT * FROM evidence ORDER BY date_added DESC LIMIT ? OFFSET ?",
        (limit, offset),
    ).fetchall()
    return total, [_row_to_record(r) for r in rows]


# ── helpers ───────────────────────────────────────────────────────────────────

def _row_to_record(row: sqlite3.Row) -> EvidenceRecord:
    d = dict(row)
    d["tags"] = json.loads(d.get("tags") or "[]")
    d["human_review_flag"] = bool(d.get("human_review_flag", 0))
    return EvidenceRecord(**d)
