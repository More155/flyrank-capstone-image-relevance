"""Text embeddings via Gemini — one model, one call shape, used for both
image captions and post text (BRIEF.md is explicit: same model for both,
non-negotiable, or cosine comparisons between the two spaces are meaningless).

task_type=SEMANTIC_SIMILARITY: captions and posts are compared symmetrically
("how alike are these two pieces of text"), not query→document retrieval,
so this is the task type that actually matches what matching.py does with
the result.
"""

from __future__ import annotations

from dataclasses import dataclass

from google import genai
from google.genai import types

from config import settings

_client = genai.Client(api_key=settings.gemini_api_key)

# $ per input token. Embeddings have no output-token cost. Source:
# ai.google.dev/gemini-api/docs/pricing, checked 2026-08-03.
_PRICING_PER_INPUT_TOKEN_USD: dict[str, float] = {
    "gemini-embedding-001": 0.15e-6,
}
_FALLBACK_PRICING_USD = _PRICING_PER_INPUT_TOKEN_USD["gemini-embedding-001"]


@dataclass
class EmbeddingResult:
    vector: list[float]
    input_tokens: int
    cost_usd: float
    model: str


async def embed_text(text: str) -> EmbeddingResult:
    resp = await _client.aio.models.embed_content(
        model=settings.embedding_model,
        contents=text,
        config=types.EmbedContentConfig(
            output_dimensionality=settings.embedding_dimensions,
            task_type="SEMANTIC_SIMILARITY",
        ),
    )
    vector = resp.embeddings[0].values

    # embed_content returns no usage_metadata at all in this SDK version
    # (verified live — resp.metadata is None), unlike generate_content.
    # Estimate tokens from input length using Gemini's own documented
    # ~4-characters-per-token rule of thumb, so cost tracking has a real
    # (if approximate) number instead of silently logging 0.
    input_tokens = max(1, len(text) // 4)

    pricing = _PRICING_PER_INPUT_TOKEN_USD.get(settings.embedding_model, _FALLBACK_PRICING_USD)
    cost_usd = input_tokens * pricing

    return EmbeddingResult(
        vector=vector,
        input_tokens=input_tokens,
        cost_usd=cost_usd,
        model=settings.embedding_model,
    )
