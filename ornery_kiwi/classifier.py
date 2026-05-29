import json
import logging
import re
from pathlib import Path

from .config import (
    ANTHROPIC_API_KEY, CLAUDE_MODEL,
    OPENAI_API_KEY, OPENAI_MODEL,
    AI_PROVIDER, VIABILITY_CATEGORIES,
)

logger = logging.getLogger(__name__)

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
    if AI_PROVIDER == "openai":
        return _classify_openai(file_path, transcript, image_text, image_description, image_entities, file_type)
    return _classify_claude(file_path, transcript, image_text, image_description, image_entities, file_type)


# ── shared helpers ────────────────────────────────────────────────────────────

def _build_prompt(file_path: Path, transcript, image_text, image_description, image_entities, file_type) -> str | None:
    parts = [f"File: {Path(file_path).name}", f"Type: {file_type}"]
    if transcript:
        parts.append(f"\n### Video Transcript\n{transcript}")
    if image_text:
        parts.append(f"\n### Extracted Image Text\n{image_text}")
    if image_description:
        parts.append(f"\n### Image Description\n{image_description}")
    if image_entities:
        parts.append(f"\n### Identified Entities\n{image_entities}")

    if not any([transcript, image_text, image_description]):
        return None

    return _CLASSIFY_PROMPT.format(
        content_block="\n".join(parts),
        categories=", ".join(VIABILITY_CATEGORIES),
    )


def _parse_response(raw: str) -> dict:
    try:
        result = json.loads(raw.strip())
        result["error"] = None
        return result
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            try:
                result = json.loads(match.group())
                result["error"] = None
                return result
            except json.JSONDecodeError:
                pass
    return _empty_result("Failed to parse classification response")


def _empty_result(reason: str) -> dict:
    return {
        "title": "Untitled", "summary": reason, "category": "Other",
        "secondary_categories": [], "key_topics": [], "sentiment": "neutral",
        "target_audience": "Unknown", "viability_score": 0,
        "viability_reasoning": reason, "content_flags": [],
        "recommended_tags": [], "error": reason,
    }


# ── Claude ────────────────────────────────────────────────────────────────────

_anthropic_client = None


def _get_anthropic():
    global _anthropic_client
    if _anthropic_client is None:
        import anthropic
        _anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    return _anthropic_client


def _classify_claude(file_path, transcript, image_text, image_description, image_entities, file_type) -> dict:
    prompt = _build_prompt(file_path, transcript, image_text, image_description, image_entities, file_type)
    if not prompt:
        return _empty_result("No extractable content found")

    logger.info(f"[Claude] Classifying {Path(file_path).name}")
    client = _get_anthropic()
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text if response.content else "{}"
    return _parse_response(raw)


# ── OpenAI ────────────────────────────────────────────────────────────────────

_openai_client = None


def _get_openai():
    global _openai_client
    if _openai_client is None:
        from openai import OpenAI
        _openai_client = OpenAI(api_key=OPENAI_API_KEY)
    return _openai_client


def _classify_openai(file_path, transcript, image_text, image_description, image_entities, file_type) -> dict:
    prompt = _build_prompt(file_path, transcript, image_text, image_description, image_entities, file_type)
    if not prompt:
        return _empty_result("No extractable content found")

    logger.info(f"[OpenAI] Classifying {Path(file_path).name}")
    client = _get_openai()
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    raw = response.choices[0].message.content if response.choices else "{}"
    return _parse_response(raw)
