import base64
import logging
from pathlib import Path

from .config import (
    ANTHROPIC_API_KEY, CLAUDE_MODEL,
    OPENAI_API_KEY, OPENAI_MODEL,
    AI_PROVIDER,
)

logger = logging.getLogger(__name__)


def extract_image_text(image_path: Path) -> dict:
    """Use AI vision to extract text and describe content in an image."""
    if AI_PROVIDER == "openai":
        return _extract_openai(image_path)
    return _extract_claude(image_path)


# ── shared helpers ────────────────────────────────────────────────────────────

_MEDIA_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/png",
    ".tiff": "image/png",
}

_PROMPT = (
    "Please analyze this image and provide:\n"
    "1. ALL visible text (verbatim, preserving layout where possible)\n"
    "2. A concise description of the visual content\n"
    "3. Any logos, brand names, or identifiable entities\n\n"
    "Format your response as:\n"
    "## Extracted Text\n<text or 'No text found'>\n\n"
    "## Visual Description\n<description>\n\n"
    "## Entities & Brands\n<list or 'None identified'>"
)


def _load_image(image_path: Path) -> tuple[bytes, str]:
    suffix = image_path.suffix.lower()
    if suffix in {".bmp", ".tiff"}:
        from PIL import Image
        import io
        img = Image.open(image_path).convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue(), "image/png"
    media_type = _MEDIA_TYPES.get(suffix)
    if not media_type:
        raise ValueError(f"Unsupported image format: {suffix}")
    return image_path.read_bytes(), media_type


def _parse_section(text: str, header: str) -> str:
    lines = text.split("\n")
    collecting, result = False, []
    for line in lines:
        if line.strip().startswith(header):
            collecting = True
            continue
        if collecting:
            if line.startswith("## "):
                break
            result.append(line)
    return "\n".join(result).strip()


# ── Claude ────────────────────────────────────────────────────────────────────

_anthropic_client = None


def _get_anthropic():
    global _anthropic_client
    if _anthropic_client is None:
        import anthropic
        _anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    return _anthropic_client


def _extract_claude(image_path: Path) -> dict:
    image_path = Path(image_path)
    image_bytes, media_type = _load_image(image_path)
    b64 = base64.standard_b64encode(image_bytes).decode()

    client = _get_anthropic()
    logger.info(f"[Claude] Vision: {image_path.name}")
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}},
                {"type": "text", "text": _PROMPT},
            ],
        }],
    )
    raw = response.content[0].text if response.content else ""
    return _parse_raw(raw)


# ── OpenAI ────────────────────────────────────────────────────────────────────

_openai_client = None


def _get_openai():
    global _openai_client
    if _openai_client is None:
        from openai import OpenAI
        _openai_client = OpenAI(api_key=OPENAI_API_KEY)
    return _openai_client


def _extract_openai(image_path: Path) -> dict:
    image_path = Path(image_path)
    image_bytes, media_type = _load_image(image_path)
    b64 = base64.standard_b64encode(image_bytes).decode()
    data_url = f"data:{media_type};base64,{b64}"

    client = _get_openai()
    logger.info(f"[OpenAI] Vision: {image_path.name}")
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": data_url, "detail": "high"}},
                {"type": "text", "text": _PROMPT},
            ],
        }],
    )
    raw = response.choices[0].message.content if response.choices else ""
    return _parse_raw(raw)


def _parse_raw(raw: str) -> dict:
    return {
        "raw": raw,
        "text": _parse_section(raw, "## Extracted Text"),
        "description": _parse_section(raw, "## Visual Description"),
        "entities": _parse_section(raw, "## Entities & Brands"),
        "error": None,
    }
