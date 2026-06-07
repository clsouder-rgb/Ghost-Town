"""
Text extraction for the Evidence Library drop folder.

Supported formats (no API key required — all local):
  .pdf    pypdf, with pdftotext fallback (brew install poppler)
  .docx   python-docx
  .xlsx   openpyxl
  .pptx   python-pptx
  .csv    stdlib
  .html   stdlib html.parser
  .rtf    regex tag stripping (no extra deps)
  .txt / .md / .text   plain read
"""

import csv
import html as html_stdlib
import io
import logging
import re
import shutil
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {
    ".pdf", ".docx", ".xlsx", ".pptx",
    ".csv", ".html", ".htm", ".rtf",
    ".txt", ".md", ".text",
}


def extract_text(file_path: Path) -> tuple[str, Optional[str]]:
    """
    Extract plain text from a file.
    Returns (text, error_message). error_message is None on success.
    """
    path = Path(file_path)
    if not path.exists():
        return "", f"File not found: {path}"

    suffix = path.suffix.lower()
    dispatch = {
        ".pdf":   _extract_pdf,
        ".docx":  _extract_docx,
        ".xlsx":  _extract_xlsx,
        ".pptx":  _extract_pptx,
        ".csv":   _extract_csv,
        ".html":  _extract_html,
        ".htm":   _extract_html,
        ".rtf":   _extract_rtf,
    }
    if suffix in dispatch:
        return dispatch[suffix](path)
    if suffix in {".txt", ".md", ".text"}:
        return _extract_plain(path)
    return "", f"Unsupported format: {suffix}. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"


# ── PDF ───────────────────────────────────────────────────────────────────────

def _extract_pdf(path: Path) -> tuple[str, Optional[str]]:
    # Try pypdf first; fall back to pdftotext (poppler) if pypdf's native
    # extension is broken (raises BaseException, not just ImportError).
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        pages = [page.extract_text() or "" for page in reader.pages]
        text = "\n\n".join(p for p in pages if p.strip())
        if text.strip():
            return text, None
    except BaseException:
        pass
    return _extract_pdf_pdftotext(path)


def _extract_pdf_pdftotext(path: Path) -> tuple[str, Optional[str]]:
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


# ── DOCX ──────────────────────────────────────────────────────────────────────

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


# ── XLSX ──────────────────────────────────────────────────────────────────────

def _extract_xlsx(path: Path) -> tuple[str, Optional[str]]:
    try:
        import openpyxl
    except ImportError:
        return "", "openpyxl not installed. Run: pip install openpyxl"
    try:
        wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
        lines = []
        for sheet in wb.worksheets:
            lines.append(f"[Sheet: {sheet.title}]")
            for row in sheet.iter_rows(values_only=True):
                cells = [str(c) if c is not None else "" for c in row]
                line = "\t".join(cells).strip()
                if line:
                    lines.append(line)
        text = "\n".join(lines)
        if not text.strip():
            return "", "XLSX contained no extractable text"
        return text, None
    except Exception as exc:
        return "", f"XLSX extraction failed: {exc}"


# ── PPTX ──────────────────────────────────────────────────────────────────────

def _extract_pptx(path: Path) -> tuple[str, Optional[str]]:
    try:
        from pptx import Presentation
    except ImportError:
        return "", "python-pptx not installed. Run: pip install python-pptx"
    try:
        prs = Presentation(str(path))
        lines = []
        for i, slide in enumerate(prs.slides, 1):
            slide_lines = []
            for shape in slide.shapes:
                if hasattr(shape, "text") and shape.text.strip():
                    slide_lines.append(shape.text.strip())
            if slide_lines:
                lines.append(f"[Slide {i}]")
                lines.extend(slide_lines)
        text = "\n".join(lines)
        if not text.strip():
            return "", "PPTX contained no extractable text"
        return text, None
    except Exception as exc:
        return "", f"PPTX extraction failed: {exc}"


# ── CSV ───────────────────────────────────────────────────────────────────────

def _extract_csv(path: Path) -> tuple[str, Optional[str]]:
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
        reader = csv.reader(io.StringIO(raw))
        lines = ["\t".join(row) for row in reader if any(c.strip() for c in row)]
        text = "\n".join(lines)
        if not text.strip():
            return "", "CSV contained no extractable text"
        return text, None
    except Exception as exc:
        return "", f"CSV extraction failed: {exc}"


# ── HTML ──────────────────────────────────────────────────────────────────────

def _extract_html(path: Path) -> tuple[str, Optional[str]]:
    try:
        from html.parser import HTMLParser

        class _Stripper(HTMLParser):
            SKIP_TAGS = {"script", "style", "head", "meta", "link"}

            def __init__(self):
                super().__init__()
                self._skip = 0
                self.chunks: list[str] = []

            def handle_starttag(self, tag, attrs):
                if tag.lower() in self.SKIP_TAGS:
                    self._skip += 1

            def handle_endtag(self, tag):
                if tag.lower() in self.SKIP_TAGS:
                    self._skip = max(0, self._skip - 1)

            def handle_data(self, data):
                if not self._skip and data.strip():
                    self.chunks.append(data.strip())

        raw = path.read_text(encoding="utf-8", errors="replace")
        stripper = _Stripper()
        stripper.feed(raw)
        text = "\n".join(stripper.chunks)
        text = html_stdlib.unescape(text)
        if not text.strip():
            return "", "HTML contained no extractable text"
        return text, None
    except Exception as exc:
        return "", f"HTML extraction failed: {exc}"


# ── RTF ───────────────────────────────────────────────────────────────────────

def _extract_rtf(path: Path) -> tuple[str, Optional[str]]:
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
        # Strip RTF control words, groups, and binary blobs
        text = re.sub(r"\\'[0-9a-fA-F]{2}", " ", raw)   # hex-encoded chars
        text = re.sub(r"\\[a-zA-Z]+[-]?\d*[ ]?", " ", text)  # control words
        text = re.sub(r"[{}]", "", text)                  # group braces
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            return "", "RTF contained no extractable text"
        return text, None
    except Exception as exc:
        return "", f"RTF extraction failed: {exc}"


# ── Plain text ────────────────────────────────────────────────────────────────

def _extract_plain(path: Path) -> tuple[str, Optional[str]]:
    try:
        return path.read_text(encoding="utf-8", errors="replace"), None
    except Exception as exc:
        return "", f"Text read failed: {exc}"


# ── Metadata inference ────────────────────────────────────────────────────────

def infer_metadata(text: str, filename: str) -> dict:
    """
    Pull basic metadata from raw text without AI.
    Returns dict with title, summary, population_topic guesses.
    These are used as defaults — user can override at ingest time.
    """
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    title = Path(filename).stem.replace("_", " ").replace("-", " ").strip()

    summary_lines = [l for l in lines if len(l) > 30][:3]
    summary = " ".join(summary_lines)[:500] if summary_lines else text[:500]

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
