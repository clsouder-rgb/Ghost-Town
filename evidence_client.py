"""
Evidence Library client for HermesBridge / SLIPSTREAM.

Drop this file into HermesBridge and register it as a Tool.
SLIPSTREAM calls it when it needs an evidence packet during
!slip learn / !slip review / !slip monitor.

Usage inside HermesBridge:
    from evidence_client import EvidenceClient
    evidence = EvidenceClient()                          # uses default localhost:8000
    evidence = EvidenceClient("http://mac-mini.local:8000")  # remote Mac mini

    # Get a formatted context block ready to inject into a SLIPSTREAM prompt:
    context = evidence.query("semaglutide cardiovascular outcomes")

    # Search for specific packets:
    packets = evidence.search("GLP-1", tags=["cardiovascular"], limit=5)

    # Get one packet by ID:
    packet = evidence.get_packet("uuid-here")

    # Ingest a new document manually:
    evidence.ingest(title="...", source_type="article", summary="...", tags=["tag"])

    # Mark an item as human-reviewed:
    evidence.mark_reviewed("uuid-here", confidence="high")
"""

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional


class EvidenceClientError(Exception):
    pass


class EvidenceClient:
    """
    Thin HTTP client for the Evidence Library API.
    No third-party dependencies — uses stdlib urllib only.
    Safe to embed in HermesBridge without bloating the environment.
    """

    def __init__(self, base_url: str = "http://127.0.0.1:8000"):
        self.base_url = base_url.rstrip("/")

    # ── Primary SLIPSTREAM interface ──────────────────────────────────────────

    def query(self, q: str, limit: int = 5) -> str:
        """
        Best call for SLIPSTREAM to make.
        Returns a pre-formatted text block ready to inject into a prompt.
        Keeps context window small — no full reports dumped in.

        Example:
            context = evidence.query("statin therapy elderly")
            prompt = f"Answer using this evidence:\\n{context}\\n\\nQuestion: {user_question}"
        """
        params = urllib.parse.urlencode({"q": q, "limit": limit})
        return self._get(f"/evidence/query?{params}", raw=True)

    def search(
        self,
        q: Optional[str] = None,
        tags: Optional[list[str]] = None,
        source_type: Optional[str] = None,
        human_review: bool = False,
        limit: int = 10,
    ) -> list[dict]:
        """
        Search and return a list of compact evidence packets as dicts.
        Use when you need to inspect individual results before injecting.
        """
        params: dict = {"limit": limit}
        if q:
            params["q"] = q
        if tags:
            params["tags"] = ",".join(tags)
        if source_type:
            params["source_type"] = source_type
        if human_review:
            params["human_review"] = "true"
        qs = urllib.parse.urlencode(params)
        result = self._get(f"/evidence/search?{qs}")
        return result.get("packets", [])

    def get_packet(self, evidence_id: str) -> dict:
        """Fetch one compact evidence packet by ID."""
        return self._get(f"/evidence/packet/{evidence_id}")

    def catalog(self, limit: int = 50) -> list[dict]:
        """List all evidence records — lightweight catalog view."""
        result = self._get(f"/evidence/catalog?limit={limit}")
        return result.get("entries", [])

    # ── Ingest ────────────────────────────────────────────────────────────────

    def ingest(
        self,
        title: str,
        source_type: str = "other",
        summary: Optional[str] = None,
        key_findings: Optional[str] = None,
        limitations: Optional[str] = None,
        citation: Optional[str] = None,
        population_topic: Optional[str] = None,
        tags: Optional[list[str]] = None,
        date_published: Optional[str] = None,
        confidence_flag: str = "unknown",
        raw_content: Optional[str] = None,
    ) -> dict:
        """Manually ingest a document into the Evidence Library."""
        body = {
            "title": title,
            "source_type": source_type,
            "tags": tags or [],
            "confidence_flag": confidence_flag,
        }
        for k, v in [
            ("summary", summary), ("key_findings", key_findings),
            ("limitations", limitations), ("citation", citation),
            ("population_topic", population_topic),
            ("date_published", date_published), ("raw_content", raw_content),
        ]:
            if v is not None:
                body[k] = v
        return self._post("/evidence/ingest", body)

    def mark_reviewed(
        self,
        evidence_id: str,
        human_review_flag: bool = True,
        confidence_flag: Optional[str] = None,
        recency_flag: Optional[str] = None,
        limitations: Optional[str] = None,
    ) -> dict:
        """Mark an evidence item as human-reviewed."""
        body: dict = {"human_review_flag": human_review_flag}
        if confidence_flag:
            body["confidence_flag"] = confidence_flag
        if recency_flag:
            body["recency_flag"] = recency_flag
        if limitations:
            body["limitations"] = limitations
        return self._patch(f"/evidence/{evidence_id}/review", body)

    def health(self) -> dict:
        """Check that the server is reachable."""
        return self._get("/health")

    # ── HTTP helpers ──────────────────────────────────────────────────────────

    def _get(self, path: str, raw: bool = False):
        url = self.base_url + path
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                body = resp.read().decode()
                if raw:
                    return body.strip('"').replace('\\n', '\n')
                return json.loads(body)
        except urllib.error.HTTPError as e:
            raise EvidenceClientError(f"HTTP {e.code} on GET {path}: {e.read().decode()}")
        except Exception as e:
            raise EvidenceClientError(f"GET {path} failed: {e}")

    def _post(self, path: str, body: dict):
        return self._request("POST", path, body)

    def _patch(self, path: str, body: dict):
        return self._request("PATCH", path, body)

    def _request(self, method: str, path: str, body: dict):
        url = self.base_url + path
        data = json.dumps(body).encode()
        req = urllib.request.Request(
            url, data=data, method=method,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            raise EvidenceClientError(f"HTTP {e.code} on {method} {path}: {e.read().decode()}")
        except Exception as e:
            raise EvidenceClientError(f"{method} {path} failed: {e}")


# ── SLIPSTREAM Tool registration stub ─────────────────────────────────────────
#
# In HermesBridge, register this as a Tool in your FSTS config:
#
#   tools:
#     evidence:
#       module: evidence_client
#       class: EvidenceClient
#       base_url: http://127.0.0.1:8000
#
# Then in a Skill (learn / review / monitor), call it as:
#
#   context = tools.evidence.query(mission_topic)
#   # inject context into the Gemma prompt before reasoning
#
# The `query()` method is the primary integration point.
# It returns the smallest useful evidence block for the prompt.
