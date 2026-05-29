import json
import logging
from pathlib import Path

import anthropic

from .config import ANTHROPIC_API_KEY, CLAUDE_MODEL, VIABILITY_CATEGORIES

logger = logging.getLogger(__name__)

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    return _client


_CLASSIFY_PROMPT = """\
You are a media content analyst. Analyze the provided content extracted from a media file and return a structured JSON assessment.

Content to analyze:
{content_block}

Return ONLY valid JSON matching this schema (no markdown fences):
{{
  "title": "<inferred descriptive title for this content, max 10 words>",
  "summary": "<2-3 sentence summary of the content>",
  "category": "<best matching category from the list>",
  "secondary_categories": ["<other relevant categories>"],
  "key_topics": ["<topic1>", "<topic2>", "<topic3>"],
  "sentiment": "<positive|neutral|negative|mixed>",
  "target_audience": "<description of likely target audience>",
  "viability_score": <integer 1-10>,
  "viability_reasoning": "<2-3 sentences explaining the viability score>",
  "content_flags": ["<any concerns: explicit, misleading, low-quality, etc. Empty array if none>"],
  "recommended_tags": ["<tag1>", "<tag2>", "<tag3>", "<tag4>", "<tag5>"]
}}

Viability score guide:
1-3: Low quality, misleading, or very limited use case
4-6: Average content with moderate value or reach potential
7-8: High quality, clear value proposition, strong audience fit
9-10: Exceptional content with viral or high-impact potential

Valid categories: {categories}
"""


def classify_content(
    file_path: Path,
    transcript: str = "",
    image_text: str = "",
    image_description: str = "",
    image_entities: str = "",
    file_type: str = "video",
) -> dict:
    """Classify media content and return viability scoring via Claude."""
    file_path = Path(file_path)

    content_parts = []
    content_parts.append(f"File: {file_path.name}")
    content_parts.append(f"Type: {file_type}")

    if transcript:
        content_parts.append(f"\n### Video Transcript\n{transcript}")
    if image_text:
        content_parts.append(f"\n### Extracted Image Text\n{image_text}")
    if image_description:
        content_parts.append(f"\n### Image Description\n{image_description}")
    if image_entities:
        content_parts.append(f"\n### Identified Entities\n{image_entities}")

    if not any([transcript, image_text, image_description]):
        return _empty_result("No extractable content found")

    content_block = "\n".join(content_parts)
    prompt = _CLASSIFY_PROMPT.format(
        content_block=content_block,
        categories=", ".join(VIABILITY_CATEGORIES),
    )

    client = _get_client()
    logger.info(f"Classifying content for {file_path.name}")

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text if response.content else "{}"
    try:
        result = json.loads(raw.strip())
        result["error"] = None
        return result
    except json.JSONDecodeError:
        logger.warning(f"Failed to parse JSON response, attempting extraction")
        return _extract_json_fallback(raw)


def _empty_result(reason: str) -> dict:
    return {
        "title": "Untitled",
        "summary": reason,
        "category": "Other",
        "secondary_categories": [],
        "key_topics": [],
        "sentiment": "neutral",
        "target_audience": "Unknown",
        "viability_score": 0,
        "viability_reasoning": reason,
        "content_flags": [],
        "recommended_tags": [],
        "error": reason,
    }


def _extract_json_fallback(text: str) -> dict:
    import re
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        try:
            result = json.loads(match.group())
            result["error"] = None
            return result
        except json.JSONDecodeError:
            pass
    return _empty_result("Failed to parse classification response")
