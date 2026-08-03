"""Vision tagging via Gemini Flash structured output.

Split into three pieces on purpose: `tag_image` does the network call,
`parse_vision_output` validates raw JSON, `derive_status` maps a validated
(or missing) result to a `TagStatus`. The last two are pure and covered by
tests without touching the network; `tag_image` is exercised by the batch
job (`jobs/classify.py`), which owns retries.
"""

from __future__ import annotations

from dataclasses import dataclass

from google import genai
from google.genai import types
from pydantic import ValidationError

from config import (
    FALLBACK_GENERATE_CONTENT_PRICING_USD,
    GENERATE_CONTENT_PRICING_USD,
    settings,
)
from schemas import TagStatus, VisionTagOutput
from vocab import Subject, prompt_vocab_block

_client = genai.Client(api_key=settings.gemini_api_key)

_PROMPT_TEMPLATE = """Identify the main animal subject in this image using \
the controlled vocabulary below. Pick the closest canonical id, or \
"unknown" if none fit or you are not confident.

{vocab}

Return structured tags: subject, category, attributes (short, lowercase \
phrases), a one-sentence caption, and your confidence (0-1). If you are \
unsure, say so honestly in `reasoning` and lower `confidence` rather than \
guessing."""


@dataclass
class VisionCallResult:
    parsed: VisionTagOutput | None
    raw_text: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    model_version: str
    error: str | None


def parse_vision_output(raw_text: str) -> tuple[VisionTagOutput | None, str | None]:
    """Validate raw model JSON against the schema. Never raises."""
    try:
        return VisionTagOutput.model_validate_json(raw_text), None
    except ValidationError as exc:
        return None, str(exc)


def derive_status(parsed: VisionTagOutput | None, conf_floor: float) -> TagStatus:
    if parsed is None:
        return TagStatus.INVALID_OUTPUT
    if parsed.subject is Subject.UNKNOWN:
        return TagStatus.UNKNOWN_SUBJECT
    if parsed.confidence < conf_floor:
        return TagStatus.LOW_CONFIDENCE
    return TagStatus.OK


async def tag_image(image_bytes: bytes, mime_type: str = "image/jpeg") -> VisionCallResult:
    """One Gemini call. Raises on transient API errors (429/5xx) so the
    caller's retry policy applies; never raises on invalid model output —
    that comes back as `parsed=None, error=...` instead.
    """
    prompt = _PROMPT_TEMPLATE.format(vocab=prompt_vocab_block())

    resp = await _client.aio.models.generate_content(
        model=settings.vision_model,
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
            prompt,
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_json_schema=VisionTagOutput.model_json_schema(),
        ),
    )

    usage = resp.usage_metadata
    input_tokens = (usage.prompt_token_count if usage else 0) or 0
    output_tokens = (
        ((usage.candidates_token_count or 0) + (usage.thoughts_token_count or 0))
        if usage
        else 0
    )
    model_version = resp.model_version or settings.vision_model
    pricing = GENERATE_CONTENT_PRICING_USD.get(model_version, FALLBACK_GENERATE_CONTENT_PRICING_USD)
    cost_usd = input_tokens * pricing["input"] + output_tokens * pricing["output"]

    parsed, error = parse_vision_output(resp.text)

    return VisionCallResult(
        parsed=parsed,
        raw_text=resp.text,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
        model_version=model_version,
        error=error,
    )
