"""Post subject extraction — same idea as vision.py, applied to text
instead of pixels (schemas.py's own docstring says so). Reuses
settings.vision_model since this is also a plain text-in/JSON-out call;
no separate model config needed for it.
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
from schemas import SubjectExtraction
from vocab import prompt_vocab_block

_client = genai.Client(api_key=settings.gemini_api_key)

_PROMPT_TEMPLATE = """A blog post has this title and body. Identify which \
single subject, from the controlled vocabulary below, the post is about.
Pick "unknown" if none fit or you are not confident — paraphrases and \
scientific names count as a match (e.g. "Vulpes vulpes" is the red fox).

{vocab}

Title: {title}

Body: {body}

Return the canonical subject id and your confidence (0-1)."""


@dataclass
class ExtractionResult:
    parsed: SubjectExtraction | None
    raw_text: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    model_version: str
    error: str | None


def parse_extraction_output(raw_text: str) -> tuple[SubjectExtraction | None, str | None]:
    try:
        return SubjectExtraction.model_validate_json(raw_text), None
    except ValidationError as exc:
        return None, str(exc)


async def extract_subject(title: str, body: str) -> ExtractionResult:
    prompt = _PROMPT_TEMPLATE.format(vocab=prompt_vocab_block(), title=title, body=body)

    resp = await _client.aio.models.generate_content(
        model=settings.vision_model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_json_schema=SubjectExtraction.model_json_schema(),
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

    parsed, error = parse_extraction_output(resp.text)

    return ExtractionResult(
        parsed=parsed,
        raw_text=resp.text,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
        model_version=model_version,
        error=error,
    )
