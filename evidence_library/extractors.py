"""
Text extraction for the Evidence Library drop folder.
All extractors are local — no API key required.

Supported formats:
  Documents   .pdf  .docx  .txt  .md  .rtf
  Spreadsheet .xlsx  .xls  .csv  .tsv
  Slides      .pptx
  Web/data    .html  .htm  .xml  .json  .jsonl  .ndjson
  Archives    .zip  .tar  .tar.gz  .tgz  .gz
  Clinical    .xpt  .sas7bdat  .sav  .dta
  Apple       .pages  .numbers  .keynote  .webloc  .plist

Optional deps (soft-fail with install hint if missing):
  pypdf          PDF (pip install pypdf)
  python-docx    DOCX (pip install python-docx)
  openpyxl       XLSX (pip install openpyxl)
  xlrd           XLS legacy (pip install xlrd)
  python-pptx    PPTX (pip install python-pptx)
  pyreadstat     XPT/SAS/SPSS/Stata (pip install pyreadstat)
  numbers-parser Apple Numbers newer format (pip install numbers-parser)
  poppler-utils  pdftotext fallback (brew install poppler)
"""

import csv
import gzip
import html as html_stdlib
import io
import json
import logging
import plistlib
import re
import shutil
import subprocess
import tarfile
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {
    # Documents
    ".pdf", ".docx", ".txt", ".md", ".text", ".rtf",
    # Spreadsheets
    ".xlsx", ".xls", ".csv", ".tsv",
    # Presentations
    ".pptx",
    # Web / data
    ".html", ".htm", ".xml", ".json", ".jsonl", ".ndjson",
    # Archives (contents are recursively extracted)
    ".zip", ".tar", ".gz", ".tgz",
    # Clinical trial / statistical formats
    ".xpt", ".sas7bdat", ".sav", ".dta",
    # Apple-native
    ".pages", ".numbers", ".keynote", ".webloc", ".plist",
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
    name_lower = path.name.lower()

    # .tar.gz / .tgz treated as archives regardless of final suffix
    if name_lower.endswith(".tar.gz") or suffix == ".tgz":
        return _extract_archive_tar(path)

    dispatch = {
        # Documents
        ".pdf":      _extract_pdf,
        ".docx":     _extract_docx,
        ".rtf":      _extract_rtf,
        # Spreadsheets
        ".xlsx":     _extract_xlsx,
        ".xls":      _extract_xls,
        ".csv":      _extract_csv,
        ".tsv":      _extract_tsv,
        # Presentations
        ".pptx":     _extract_pptx,
        # Web / data
        ".html":     _extract_html,
        ".htm":      _extract_html,
        ".xml":      _extract_xml,
        ".json":     _extract_json,
        ".jsonl":    _extract_jsonl,
        ".ndjson":   _extract_jsonl,
        # Archives
        ".zip":      _extract_archive_zip,
        ".tar":      _extract_archive_tar,
        ".gz":       _extract_archive_gz,
        # Clinical
        ".xpt":      _extract_clinical,
        ".sas7bdat": _extract_clinical,
        ".sav":      _extract_clinical,
        ".dta":      _extract_clinical,
        # Apple
        ".pages":    _extract_apple_iwork,
        ".numbers":  _extract_apple_numbers,
        ".keynote":  _extract_apple_iwork,
        ".webloc":   _extract_webloc,
        ".plist":    _extract_plist,
    }

    if suffix in dispatch:
        return dispatch[suffix](path)
    if suffix in {".txt", ".md", ".text"}:
        return _extract_plain(path)
    return "", f"Unsupported format: {suffix}. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"


# ── PDF ───────────────────────────────────────────────────────────────────────

def _extract_pdf(path: Path) -> tuple[str, Optional[str]]:
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


# ── XLSX / XLS ────────────────────────────────────────────────────────────────

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


def _extract_xls(path: Path) -> tuple[str, Optional[str]]:
    try:
        import xlrd
    except ImportError:
        return "", "xlrd not installed. Run: pip install xlrd"
    try:
        wb = xlrd.open_workbook(str(path))
        lines = []
        for sheet in wb.sheets():
            lines.append(f"[Sheet: {sheet.name}]")
            for rx in range(sheet.nrows):
                row = [str(sheet.cell_value(rx, cx)) for cx in range(sheet.ncols)]
                line = "\t".join(row).strip()
                if line:
                    lines.append(line)
        text = "\n".join(lines)
        if not text.strip():
            return "", "XLS contained no extractable text"
        return text, None
    except Exception as exc:
        return "", f"XLS extraction failed: {exc}"


# ── CSV / TSV ─────────────────────────────────────────────────────────────────

def _extract_csv(path: Path) -> tuple[str, Optional[str]]:
    return _read_delimited(path, delimiter=",")


def _extract_tsv(path: Path) -> tuple[str, Optional[str]]:
    return _read_delimited(path, delimiter="\t")


def _read_delimited(path: Path, delimiter: str) -> tuple[str, Optional[str]]:
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
        reader = csv.reader(io.StringIO(raw), delimiter=delimiter)
        lines = ["\t".join(row) for row in reader if any(c.strip() for c in row)]
        text = "\n".join(lines)
        if not text.strip():
            return "", f"{path.suffix.upper()} contained no extractable text"
        return text, None
    except Exception as exc:
        return "", f"{path.suffix.upper()} extraction failed: {exc}"


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
            slide_lines = [
                shape.text.strip()
                for shape in slide.shapes
                if hasattr(shape, "text") and shape.text.strip()
            ]
            if slide_lines:
                lines.append(f"[Slide {i}]")
                lines.extend(slide_lines)
        text = "\n".join(lines)
        if not text.strip():
            return "", "PPTX contained no extractable text"
        return text, None
    except Exception as exc:
        return "", f"PPTX extraction failed: {exc}"


# ── HTML ──────────────────────────────────────────────────────────────────────

def _extract_html(path: Path) -> tuple[str, Optional[str]]:
    try:
        from html.parser import HTMLParser

        class _Stripper(HTMLParser):
            SKIP = {"script", "style", "head", "meta", "link", "noscript"}

            def __init__(self):
                super().__init__()
                self._skip = 0
                self.chunks: list[str] = []

            def handle_starttag(self, tag, attrs):
                if tag.lower() in self.SKIP:
                    self._skip += 1

            def handle_endtag(self, tag):
                if tag.lower() in self.SKIP:
                    self._skip = max(0, self._skip - 1)

            def handle_data(self, data):
                if not self._skip and data.strip():
                    self.chunks.append(data.strip())

        raw = path.read_text(encoding="utf-8", errors="replace")
        s = _Stripper()
        s.feed(raw)
        text = html_stdlib.unescape("\n".join(s.chunks))
        if not text.strip():
            return "", "HTML contained no extractable text"
        return text, None
    except Exception as exc:
        return "", f"HTML extraction failed: {exc}"


# ── XML ───────────────────────────────────────────────────────────────────────

def _extract_xml(path: Path) -> tuple[str, Optional[str]]:
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
        tree = ET.fromstring(raw)
        chunks = [t.strip() for t in tree.itertext() if t.strip()]
        text = "\n".join(chunks)
        if not text.strip():
            return "", "XML contained no extractable text"
        return text, None
    except Exception as exc:
        # Fall back to regex tag stripping if XML is malformed
        try:
            raw = path.read_text(encoding="utf-8", errors="replace")
            text = re.sub(r"<[^>]+>", " ", raw)
            text = re.sub(r"\s+", " ", text).strip()
            return (text, None) if text else ("", "XML contained no extractable text")
        except Exception:
            return "", f"XML extraction failed: {exc}"


# ── JSON ──────────────────────────────────────────────────────────────────────

def _extract_json(path: Path) -> tuple[str, Optional[str]]:
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
        data = json.loads(raw)
        text = _flatten_json(data)
        if not text.strip():
            return "", "JSON contained no extractable text"
        return text, None
    except Exception as exc:
        return "", f"JSON extraction failed: {exc}"


def _extract_jsonl(path: Path) -> tuple[str, Optional[str]]:
    try:
        lines = []
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line:
                try:
                    lines.append(_flatten_json(json.loads(line)))
                except json.JSONDecodeError:
                    lines.append(line)
        text = "\n".join(lines)
        if not text.strip():
            return "", "JSONL contained no extractable text"
        return text, None
    except Exception as exc:
        return "", f"JSONL extraction failed: {exc}"


def _flatten_json(obj, depth: int = 0) -> str:
    if depth > 6:
        return str(obj)
    if isinstance(obj, dict):
        parts = []
        for k, v in obj.items():
            inner = _flatten_json(v, depth + 1)
            if inner.strip():
                parts.append(f"{k}: {inner}")
        return "\n".join(parts)
    if isinstance(obj, list):
        return "\n".join(_flatten_json(i, depth + 1) for i in obj if i not in (None, "", [], {}))
    return str(obj) if obj not in (None, "") else ""


# ── RTF ───────────────────────────────────────────────────────────────────────

def _extract_rtf(path: Path) -> tuple[str, Optional[str]]:
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
        text = re.sub(r"\\'[0-9a-fA-F]{2}", " ", raw)
        text = re.sub(r"\\[a-zA-Z]+[-]?\d*[ ]?", " ", text)
        text = re.sub(r"[{}]", "", text)
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            return "", "RTF contained no extractable text"
        return text, None
    except Exception as exc:
        return "", f"RTF extraction failed: {exc}"


# ── Archives ──────────────────────────────────────────────────────────────────

def _extract_archive_zip(path: Path) -> tuple[str, Optional[str]]:
    try:
        parts = []
        with zipfile.ZipFile(str(path), "r") as zf:
            with tempfile.TemporaryDirectory() as tmpdir:
                zf.extractall(tmpdir)
                parts = _extract_dir(Path(tmpdir), source_label=path.name)
        if not parts:
            return "", f"ZIP archive contained no supported files"
        return "\n\n".join(parts), None
    except Exception as exc:
        return "", f"ZIP extraction failed: {exc}"


def _extract_archive_tar(path: Path) -> tuple[str, Optional[str]]:
    try:
        mode = "r:gz" if str(path).lower().endswith((".tar.gz", ".tgz")) else "r:*"
        with tarfile.open(str(path), mode) as tf:
            with tempfile.TemporaryDirectory() as tmpdir:
                tf.extractall(tmpdir)
                parts = _extract_dir(Path(tmpdir), source_label=path.name)
        if not parts:
            return "", "TAR archive contained no supported files"
        return "\n\n".join(parts), None
    except Exception as exc:
        return "", f"TAR extraction failed: {exc}"


def _extract_archive_gz(path: Path) -> tuple[str, Optional[str]]:
    # Single-file gzip (e.g. data.csv.gz) — detect inner type from stem
    inner_suffix = Path(path.stem).suffix.lower()
    if not inner_suffix:
        inner_suffix = ".txt"
    try:
        with gzip.open(str(path), "rb") as gz:
            raw = gz.read()
        with tempfile.NamedTemporaryFile(suffix=inner_suffix, delete=False) as tmp:
            tmp.write(raw)
            tmp_path = Path(tmp.name)
        try:
            return extract_text(tmp_path)
        finally:
            tmp_path.unlink(missing_ok=True)
    except Exception as exc:
        return "", f"GZ extraction failed: {exc}"


def _extract_dir(directory: Path, source_label: str = "") -> list[str]:
    """Recursively extract text from all supported files in a directory."""
    parts = []
    for p in sorted(directory.rglob("*")):
        if not p.is_file():
            continue
        suffix = p.suffix.lower()
        name_lower = p.name.lower()
        # Skip macOS metadata files
        if p.name.startswith("._") or p.name == ".DS_Store":
            continue
        is_supported = (
            suffix in SUPPORTED_EXTENSIONS
            or name_lower.endswith(".tar.gz")
        )
        if not is_supported:
            continue
        text, err = extract_text(p)
        if err:
            logger.debug(f"[archive] {p.name}: {err}")
            continue
        if text.strip():
            rel = p.relative_to(directory)
            parts.append(f"[File: {rel}]\n{text.strip()}")
    return parts


# ── Clinical: XPT / SAS / SPSS / Stata ───────────────────────────────────────

def _extract_clinical(path: Path) -> tuple[str, Optional[str]]:
    try:
        import pyreadstat
    except ImportError:
        return "", (
            f"pyreadstat not installed — needed for {path.suffix} files. "
            "Run: pip install pyreadstat"
        )
    try:
        suffix = path.suffix.lower()
        readers = {
            ".xpt":      pyreadstat.read_xport,
            ".sas7bdat": pyreadstat.read_sas7bdat,
            ".sav":      pyreadstat.read_sav,
            ".dta":      pyreadstat.read_dta,
        }
        read_fn = readers.get(suffix)
        if not read_fn:
            return "", f"No clinical reader for {suffix}"
        df, meta = read_fn(str(path))
        lines = []
        # Variable labels as a header glossary
        if meta.column_names_to_labels:
            lines.append("[Variable Labels]")
            for col, label in meta.column_names_to_labels.items():
                lines.append(f"  {col}: {label}")
            lines.append("")
        # Column names + first rows as preview
        lines.append("[Columns]: " + ", ".join(df.columns.tolist()))
        lines.append(f"[Rows]: {len(df)}")
        lines.append("")
        preview = df.head(20).to_string(index=False)
        lines.append(preview)
        return "\n".join(lines), None
    except Exception as exc:
        return "", f"Clinical file extraction failed: {exc}"


# ── Apple: Pages / Keynote ────────────────────────────────────────────────────

def _extract_apple_iwork(path: Path) -> tuple[str, Optional[str]]:
    """
    Pages and Keynote bundles are ZIP files.
    New format (2013+): IWA protobuf inside — fall back to readable strings.
    Old format: index.xml with embedded text.
    """
    if not zipfile.is_zipfile(str(path)):
        return "", f"{path.suffix} file is not a valid ZIP bundle"
    try:
        with zipfile.ZipFile(str(path), "r") as zf:
            names = zf.namelist()

            # Old XML-based format
            xml_candidates = [n for n in names if n.endswith(".xml") and "index" in n.lower()]
            if not xml_candidates:
                xml_candidates = [n for n in names if n.endswith(".xml")]

            chunks = []
            for xml_name in xml_candidates[:3]:
                raw = zf.read(xml_name).decode("utf-8", errors="replace")
                try:
                    tree = ET.fromstring(raw)
                    chunks += [t.strip() for t in tree.itertext() if len(t.strip()) > 2]
                except ET.ParseError:
                    chunks += re.findall(r'[A-Za-z][^\x00-\x1f"<>]{10,}', raw)

            # New IWA format: extract printable strings from binary files
            if not chunks:
                for name in names:
                    if name.endswith((".iwa", ".proto")):
                        raw = zf.read(name)
                        printable = re.findall(rb'[ -~]{10,}', raw)
                        chunks += [p.decode("utf-8", errors="replace") for p in printable[:50]]

            text = "\n".join(dict.fromkeys(chunks))  # deduplicate, preserve order
            if not text.strip():
                return "", f"{path.suffix} contained no extractable text"
            return text, None
    except Exception as exc:
        return "", f"{path.suffix} extraction failed: {exc}"


# ── Apple: Numbers ────────────────────────────────────────────────────────────

def _extract_apple_numbers(path: Path) -> tuple[str, Optional[str]]:
    # Try numbers-parser for full fidelity
    try:
        import numbers_parser
        doc = numbers_parser.Document(str(path))
        lines = []
        for sheet in doc.sheets:
            lines.append(f"[Sheet: {sheet.name}]")
            for row in sheet.tables[0].iter_rows():
                cells = [str(c.value) if c.value is not None else "" for c in row]
                line = "\t".join(cells).strip()
                if line:
                    lines.append(line)
        text = "\n".join(lines)
        if text.strip():
            return text, None
    except ImportError:
        pass  # fall through to ZIP extraction
    except Exception as exc:
        logger.debug(f"numbers-parser failed for {path.name}: {exc}")

    # Fall back to ZIP-based string extraction (same as Pages/Keynote)
    return _extract_apple_iwork(path)


# ── Apple: .webloc (Safari bookmark) ─────────────────────────────────────────

def _extract_webloc(path: Path) -> tuple[str, Optional[str]]:
    try:
        raw = path.read_bytes()
        # Try binary plist first, then XML plist
        try:
            data = plistlib.loads(raw)
        except Exception:
            data = plistlib.loads(raw, fmt=plistlib.FMT_XML)
        url = data.get("URL", "")
        if not url:
            return "", "webloc contained no URL"
        return f"URL: {url}", None
    except Exception as exc:
        return "", f"webloc extraction failed: {exc}"


# ── Apple: .plist ─────────────────────────────────────────────────────────────

def _extract_plist(path: Path) -> tuple[str, Optional[str]]:
    try:
        raw = path.read_bytes()
        try:
            data = plistlib.loads(raw)
        except Exception:
            data = plistlib.loads(raw, fmt=plistlib.FMT_XML)
        text = _flatten_json(data)
        if not text.strip():
            return "", "plist contained no extractable text"
        return text, None
    except Exception as exc:
        return "", f"plist extraction failed: {exc}"


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
