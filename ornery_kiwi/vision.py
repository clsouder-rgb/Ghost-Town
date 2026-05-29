import base64
import logging
from pathlib import Path

import anthropic

from .config import ANTHROPIC_API_KEY, CLAUDE_MODEL

logger = logging.getLogger(__name__)

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    return _client


_MEDIA_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/png",   # convert via Pillow below
    ".tiff": "image/png",
}


def _load_image_bytes(image_path: Path) -> tuple[bytes, str]:
    """Return (image_bytes, media_type). Converts unsupported formats via Pillow."""
    suffix = image_path.suffix.lower()
    media_type = _MEDIA_TYPES.get(suffix)

    if suffix in {".bmp", ".tiff"}:
        from PIL import Image
        import io
        img = Image.open(image_path).convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue(), "image/png"

    if media_type is None:
        raise ValueError(f"Unsupported image format: {suffix}")

    return image_path.read_bytes(), media_type


def extract_image_text(image_path: Path) -> dict:
    """Use Claude Vision to extract text and describe content in an image."""
    image_path = Path(image_path)
    if not image_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    image_bytes, media_type = _load_image_bytes(image_path)
    b64_data = base64.standard_b64encode(image_bytes).decode("utf-8")

    client = _get_client()
    logger.info(f"Sending {image_path.name} to Claude Vision")

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": b64_data,
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            "Please analyze this image and provide:\n"
                            "1. ALL visible text (verbatim, preserving layout where possible)\n"
                            "2. A concise description of the visual content\n"
                            "3. Any logos, brand names, or identifiable entities\n\n"
                            "Format your response as:\n"
                            "## Extracted Text\n<text or 'No text found'>\n\n"
                            "## Visual Description\n<description>\n\n"
                            "## Entities & Brands\n<list or 'None identified'>"
                        ),
                    },
                ],
            }
        ],
    )

    raw = response.content[0].text if response.content else ""
    return {
        "raw": raw,
        "text": _parse_section(raw, "## Extracted Text"),
        "description": _parse_section(raw, "## Visual Description"),
        "entities": _parse_section(raw, "## Entities & Brands"),
        "error": None,
    }


def _parse_section(text: str, header: str) -> str:
    lines = text.split("\n")
    collecting = False
    result = []
    for line in lines:
        if line.strip().startswith(header):
            collecting = True
            continue
        if collecting:
            if line.startswith("## "):
                break
            result.append(line)
    return "\n".join(result).strip()
