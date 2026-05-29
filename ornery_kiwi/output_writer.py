import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH

from .config import OUTPUT_DIR

logger = logging.getLogger(__name__)


def _viability_color(score: int) -> str:
    """Map viability score to a color label."""
    if score >= 8:
        return "HIGH"
    elif score >= 5:
        return "MEDIUM"
    return "LOW"


def _score_bar(score: int, total: int = 10) -> str:
    filled = round(score / total * 10)
    return "█" * filled + "░" * (10 - filled)


def build_md(
    source_file: Path,
    file_type: str,
    transcript: str,
    image_text: str,
    image_description: str,
    image_entities: str,
    classification: dict,
    processed_at: Optional[datetime] = None,
) -> Path:
    """Write a structured Markdown report and return its path."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = (processed_at or datetime.now()).strftime("%Y%m%d_%H%M%S")
    stem = source_file.stem
    out_path = OUTPUT_DIR / f"{stem}_{ts}.md"

    score = classification.get("viability_score", 0)
    viability_label = _viability_color(score)
    bar = _score_bar(score)
    now_str = (processed_at or datetime.now()).strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        f"# {classification.get('title', stem)}",
        "",
        f"> **Processed by Ornery-Kiwi** | {now_str}",
        "",
        "---",
        "",
        "## Overview",
        "",
        f"| Field | Value |",
        f"|-------|-------|",
        f"| Source File | `{source_file.name}` |",
        f"| File Type | {file_type.capitalize()} |",
        f"| Category | {classification.get('category', 'Unknown')} |",
        f"| Sentiment | {classification.get('sentiment', 'N/A').capitalize()} |",
        f"| Target Audience | {classification.get('target_audience', 'N/A')} |",
        f"| Viability Score | {score}/10 — {viability_label} `{bar}` |",
        "",
        "---",
        "",
        "## Summary",
        "",
        classification.get("summary", "_No summary available._"),
        "",
        "---",
        "",
        "## Viability Assessment",
        "",
        f"**Score: {score}/10** ({viability_label})",
        "",
        classification.get("viability_reasoning", "_No reasoning provided._"),
        "",
    ]

    flags = classification.get("content_flags", [])
    if flags:
        lines += ["### Content Flags", ""]
        for flag in flags:
            lines.append(f"- ⚠️ {flag}")
        lines.append("")

    lines += [
        "---",
        "",
        "## Classification",
        "",
        f"**Primary Category:** {classification.get('category', 'Unknown')}",
        "",
    ]

    secondary = classification.get("secondary_categories", [])
    if secondary:
        lines.append(f"**Secondary Categories:** {', '.join(secondary)}")
        lines.append("")

    topics = classification.get("key_topics", [])
    if topics:
        lines += ["**Key Topics:**", ""]
        for t in topics:
            lines.append(f"- {t}")
        lines.append("")

    tags = classification.get("recommended_tags", [])
    if tags:
        lines += ["**Recommended Tags:**", ""]
        lines.append(" ".join(f"`#{t}`" for t in tags))
        lines.append("")

    lines += ["---", ""]

    if file_type == "video" and transcript:
        lines += [
            "## Transcript",
            "",
            transcript,
            "",
            "---",
            "",
        ]

    if file_type == "image":
        if image_text:
            lines += [
                "## Extracted Text",
                "",
                image_text,
                "",
                "---",
                "",
            ]
        if image_description:
            lines += [
                "## Visual Description",
                "",
                image_description,
                "",
            ]
        if image_entities:
            lines += [
                "## Entities & Brands",
                "",
                image_entities,
                "",
                "---",
                "",
            ]

    out_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info(f"Markdown written: {out_path}")
    return out_path


def build_docx(
    source_file: Path,
    file_type: str,
    transcript: str,
    image_text: str,
    image_description: str,
    image_entities: str,
    classification: dict,
    processed_at: Optional[datetime] = None,
) -> Path:
    """Write a formatted Word document and return its path."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = (processed_at or datetime.now()).strftime("%Y%m%d_%H%M%S")
    stem = source_file.stem
    out_path = OUTPUT_DIR / f"{stem}_{ts}.docx"

    doc = Document()
    score = classification.get("viability_score", 0)
    viability_label = _viability_color(score)
    now_str = (processed_at or datetime.now()).strftime("%Y-%m-%d %H:%M:%S")

    # Title
    title_para = doc.add_heading(classification.get("title", stem), level=0)
    title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER

    sub = doc.add_paragraph(f"Processed by Ornery-Kiwi  ·  {now_str}")
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub.runs[0].font.color.rgb = RGBColor(0x88, 0x88, 0x88)
    sub.runs[0].font.size = Pt(10)

    doc.add_paragraph()

    # Overview table
    doc.add_heading("Overview", level=1)
    table = doc.add_table(rows=1, cols=2)
    table.style = "Light Shading Accent 1"
    hdr = table.rows[0].cells
    hdr[0].text = "Field"
    hdr[1].text = "Value"

    rows_data = [
        ("Source File", source_file.name),
        ("File Type", file_type.capitalize()),
        ("Category", classification.get("category", "Unknown")),
        ("Sentiment", classification.get("sentiment", "N/A").capitalize()),
        ("Target Audience", classification.get("target_audience", "N/A")),
        ("Viability Score", f"{score}/10 — {viability_label}"),
    ]
    for field, value in rows_data:
        row = table.add_row().cells
        row[0].text = field
        row[1].text = value

    doc.add_paragraph()

    # Summary
    doc.add_heading("Summary", level=1)
    doc.add_paragraph(classification.get("summary", "No summary available."))

    # Viability
    doc.add_heading("Viability Assessment", level=1)
    score_para = doc.add_paragraph()
    run = score_para.add_run(f"Score: {score}/10  ({viability_label})")
    run.bold = True
    _color_run_by_viability(run, score)
    doc.add_paragraph(classification.get("viability_reasoning", "No reasoning provided."))

    flags = classification.get("content_flags", [])
    if flags:
        doc.add_heading("Content Flags", level=2)
        for flag in flags:
            doc.add_paragraph(f"⚠  {flag}", style="List Bullet")

    # Classification
    doc.add_heading("Classification", level=1)
    p = doc.add_paragraph()
    p.add_run("Primary Category: ").bold = True
    p.add_run(classification.get("category", "Unknown"))

    secondary = classification.get("secondary_categories", [])
    if secondary:
        p2 = doc.add_paragraph()
        p2.add_run("Secondary Categories: ").bold = True
        p2.add_run(", ".join(secondary))

    topics = classification.get("key_topics", [])
    if topics:
        doc.add_heading("Key Topics", level=2)
        for t in topics:
            doc.add_paragraph(t, style="List Bullet")

    tags = classification.get("recommended_tags", [])
    if tags:
        p3 = doc.add_paragraph()
        p3.add_run("Tags: ").bold = True
        p3.add_run("  ".join(f"#{t}" for t in tags))

    # Transcript / image content
    if file_type == "video" and transcript:
        doc.add_heading("Transcript", level=1)
        doc.add_paragraph(transcript)

    if file_type == "image":
        if image_text:
            doc.add_heading("Extracted Text", level=1)
            doc.add_paragraph(image_text)
        if image_description:
            doc.add_heading("Visual Description", level=1)
            doc.add_paragraph(image_description)
        if image_entities:
            doc.add_heading("Entities & Brands", level=1)
            doc.add_paragraph(image_entities)

    doc.save(str(out_path))
    logger.info(f"DOCX written: {out_path}")
    return out_path


def _color_run_by_viability(run, score: int):
    if score >= 8:
        run.font.color.rgb = RGBColor(0x00, 0x80, 0x00)  # green
    elif score >= 5:
        run.font.color.rgb = RGBColor(0xFF, 0x8C, 0x00)  # orange
    else:
        run.font.color.rgb = RGBColor(0xCC, 0x00, 0x00)  # red
