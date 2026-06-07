"""
Text extraction from PDF, DOCX, TXT, and MD files.
PDF extraction requires pypdf (already in requirements.txt).
DOCX extraction requires python-docx (already in requirements.txt).
"""

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md", ".text"}


def extract_text(file_path: Path) -> tuple[str, Optional[str]]:
    """
    Extract plain text from a file.
    Returns (text, error_message). error_message is None on success.
    """
    path = Path(file_path)
    if not path.exists():
        return "", f"File not found: {path}"

    suffix = path.suffix.lower()

    if suffix == ".pdf":
        return _extract_pdf(path)
    elif suffix == ".docx":
        return _extract_docx(path)
    elif suffix in {".txt", ".md", ".text"}:
        return _extract_plain(path)
    else:
        return "", f"Unsupported format: {suffix}. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"


def _extract_pdf(path: Path) -> tuple[str, Optional[str]]:
    # Try pypdf first; fall back to pdftotext (poppler-utils) if pypdf fails.
    # Catch BaseException: broken native extensions (e.g. _cffi_backend) raise
    # RuntimeError/PanicException rather than standard ImportError.
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        pages = [page.extract_text() or "" for page in reader.pages]
        text = "\n\n".join(p for p in pages if p.strip())
        if text.strip():
            return text, None
        # pypdf returned empty — fall through to pdftotext
    except BaseException:
        pass

    return _extract_pdf_pdftotext(path)


def _extract_pdf_pdftotext(path: Path) -> tuple[str, Optional[str]]:
    import shutil, subprocess
    if not shutil.which("pdftotext"):
        return "", (
            "PDF extraction failed: pypdf error and pdftotext not found. "
            "Install poppler-utils (brew install poppler / apt install poppler-utils)."
        )
    try:
        result = subprocess.run(
            ["pdftotext", str(path), "-"],
            capture_output=True, text=True, timeout=60,
        )
        text = result.stdout
        if not text.strip():
            return "", "PDF contained no extractable text (may be scanned image)"
        return text, None
    except Exception as exc:
        return "", f"PDF extraction failed: {exc}"


def _extract_docx(path: Path) -> tuple[str, Optional[str]]:
    try:
        from docx import Document
    except ImportError:
        return "", "python-docx not installed. Run: pip install python-docx"

    try:
        doc = Document(str(path))
        text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        if not text:
            return "", "DOCX contained no extractable text"
        return text, None
    except Exception as exc:
        return "", f"DOCX extraction failed: {exc}"


def _extract_plain(path: Path) -> tuple[str, Optional[str]]:
    try:
        return path.read_text(encoding="utf-8", errors="replace"), None
    except Exception as exc:
        return "", f"Text read failed: {exc}"


def infer_metadata(text: str, filename: str) -> dict:
    """
    Pull basic metadata from raw text without AI.
    Returns dict with title, summary, population_topic guesses.
    These are used as defaults — user can override at ingest time.
    """
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    # Title: filename stem, cleaned up
    title = Path(filename).stem.replace("_", " ").replace("-", " ").strip()

    # Summary: first 3 non-trivial lines (>30 chars) or first 500 chars
    summary_lines = [l for l in lines if len(l) > 30][:3]
    summary = " ".join(summary_lines)[:500] if summary_lines else text[:500]

    # Population/topic: look for common clinical study keywords in first 1000 chars
    head = text[:1000].lower()
    topics = []
    for kw in ["patient", "population", "participants", "subjects", "trial", "study",
                "randomized", "cohort", "placebo", "treatment", "intervention",
                "endpoint", "outcome", "efficacy", "safety"]:
        if kw in head:
            topics.append(kw)

    return {
        "title": title,
        "summary": summary.strip(),
        "population_topic": ", ".join(topics[:5]) if topics else None,
    }
