"""Core processing pipeline: given a file path, run the full Ornery-Kiwi pipeline."""

import logging
import shutil
from datetime import datetime
from pathlib import Path

from .config import (
    PROCESSED_DIR,
    VIDEO_EXTENSIONS,
    IMAGE_EXTENSIONS,
    WHISPER_MODEL,
)
from .transcriber import transcribe_video, get_video_duration
from .vision import extract_image_text
from .classifier import classify_content
from .output_writer import build_md, build_docx
from .drive_sync import sync_report_pair

logger = logging.getLogger(__name__)


def _evidence_ingest(file_path, file_type, classification, transcript="",
                     image_text="", image_description="", md_path=None):
    """Best-effort Evidence Library ingest — never blocks the main pipeline."""
    import os
    if os.getenv("EVIDENCE_INGEST_DISABLED"):
        logger.info(
            f"[EvidenceLibrary] Auto-ingest disabled (EVIDENCE_INGEST_DISABLED=1). "
            f"Skipping {Path(file_path).name}. Pipeline continues normally."
        )
        return
    try:
        from evidence_library.ingest import ingest_pipeline_result
        ingest_pipeline_result(
            source_file=file_path,
            file_type=file_type,
            classification=classification,
            transcript=transcript,
            image_text=image_text,
            image_description=image_description,
            md_path=md_path,
        )
    except Exception as exc:
        logger.warning(f"Evidence Library ingest skipped: {exc}")


def process_file(file_path: Path, drive_sync: bool = True) -> dict:
    """
    Full pipeline for one media file.

    Returns a result dict with keys:
      file, type, md_path, docx_path, viability_score, drive_urls, error
    """
    file_path = Path(file_path).resolve()
    suffix = file_path.suffix.lower()
    processed_at = datetime.now()

    result: dict = {
        "file": str(file_path),
        "type": None,
        "md_path": None,
        "docx_path": None,
        "viability_score": None,
        "drive_urls": {},
        "error": None,
    }

    if suffix in VIDEO_EXTENSIONS:
        result["type"] = "video"
        result.update(_process_video(file_path, processed_at, drive_sync))
    elif suffix in IMAGE_EXTENSIONS:
        result["type"] = "image"
        result.update(_process_image(file_path, processed_at, drive_sync))
    else:
        result["error"] = f"Unsupported file type: {suffix}"
        logger.warning(result["error"])

    if not result.get("error"):
        _move_to_processed(file_path)

    return result


def _process_video(file_path: Path, processed_at: datetime, drive_sync: bool) -> dict:
    logger.info(f"[VIDEO] Processing {file_path.name}")

    transcript_data = transcribe_video(file_path, WHISPER_MODEL)
    transcript = transcript_data.get("text", "")
    if transcript_data.get("error"):
        logger.warning(f"Transcription warning: {transcript_data['error']}")

    duration = get_video_duration(file_path)
    classification = classify_content(
        file_path=file_path,
        transcript=transcript,
        file_type="video",
    )

    md_path = build_md(
        source_file=file_path,
        file_type="video",
        transcript=transcript,
        image_text="",
        image_description="",
        image_entities="",
        classification=classification,
        processed_at=processed_at,
    )
    docx_path = build_docx(
        source_file=file_path,
        file_type="video",
        transcript=transcript,
        image_text="",
        image_description="",
        image_entities="",
        classification=classification,
        processed_at=processed_at,
    )

    drive_urls = {}
    if drive_sync:
        drive_urls = sync_report_pair(md_path, docx_path, subfolder=file_path.stem)

    _evidence_ingest(file_path, "video", classification, transcript=transcript, md_path=md_path)

    return {
        "md_path": str(md_path),
        "docx_path": str(docx_path),
        "viability_score": classification.get("viability_score"),
        "drive_urls": drive_urls,
        "error": classification.get("error"),
    }


def _process_image(file_path: Path, processed_at: datetime, drive_sync: bool) -> dict:
    logger.info(f"[IMAGE] Processing {file_path.name}")

    vision_data = extract_image_text(file_path)
    if vision_data.get("error"):
        logger.warning(f"Vision warning: {vision_data['error']}")

    classification = classify_content(
        file_path=file_path,
        image_text=vision_data.get("text", ""),
        image_description=vision_data.get("description", ""),
        image_entities=vision_data.get("entities", ""),
        file_type="image",
    )

    md_path = build_md(
        source_file=file_path,
        file_type="image",
        transcript="",
        image_text=vision_data.get("text", ""),
        image_description=vision_data.get("description", ""),
        image_entities=vision_data.get("entities", ""),
        classification=classification,
        processed_at=processed_at,
    )
    docx_path = build_docx(
        source_file=file_path,
        file_type="image",
        transcript="",
        image_text=vision_data.get("text", ""),
        image_description=vision_data.get("description", ""),
        image_entities=vision_data.get("entities", ""),
        classification=classification,
        processed_at=processed_at,
    )

    drive_urls = {}
    if drive_sync:
        drive_urls = sync_report_pair(md_path, docx_path, subfolder=file_path.stem)

    _evidence_ingest(
        file_path, "image", classification,
        image_text=vision_data.get("text", ""),
        image_description=vision_data.get("description", ""),
        md_path=md_path,
    )

    return {
        "md_path": str(md_path),
        "docx_path": str(docx_path),
        "viability_score": classification.get("viability_score"),
        "drive_urls": drive_urls,
        "error": classification.get("error"),
    }


def _move_to_processed(file_path: Path):
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    dest = PROCESSED_DIR / file_path.name
    if dest.exists():
        dest = PROCESSED_DIR / f"{file_path.stem}_{int(datetime.now().timestamp())}{file_path.suffix}"
    shutil.move(str(file_path), str(dest))
    logger.info(f"Moved to processed: {dest}")
