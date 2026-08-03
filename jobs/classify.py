"""Batch vision classification job — Flow A's tagging step (BRIEF.md §4).

Async, semaphore-limited, tenacity-retried on transient errors only,
idempotent (skips images already in `image_tags`), and every image's
outcome is logged to `model_calls` — including total failures, at $0/0
tokens since a failed call was never billed.

Scope note: embeddings (`image_vectors`) are Step 4, not here — tagging is
isolated first so a failure is either "my vision logic is wrong" or "my API
call is wrong," never both at once (see BRIEF.md §5's reasoning for why the
guard was built on mocks before any model call existed; same principle).
"""

from __future__ import annotations

import asyncio
import logging
import mimetypes
import urllib.request
from dataclasses import dataclass
from urllib.parse import urlparse
from uuid import UUID

from google.genai import errors as genai_errors
from tenacity import AsyncRetrying, retry_if_exception, stop_after_attempt, wait_exponential

from config import settings
from db import get_connection
from schemas import CallKind, TagStatus
from vision import VisionCallResult, derive_status, tag_image

logger = logging.getLogger(__name__)

_MAX_ATTEMPTS = 4


def _is_transient(exc: BaseException) -> bool:
    if isinstance(exc, genai_errors.ServerError):
        return True
    if isinstance(exc, genai_errors.ClientError):
        return getattr(exc, "code", None) == 429
    return False


def _load_image_bytes(source_uri: str) -> tuple[bytes, str]:
    mime_type = mimetypes.guess_type(source_uri)[0] or "image/jpeg"
    if urlparse(source_uri).scheme in ("http", "https"):
        with urllib.request.urlopen(source_uri) as resp:
            return resp.read(), mime_type
    with open(source_uri, "rb") as f:
        return f.read(), mime_type


async def _tag_with_retry(
    image_bytes: bytes,
    mime_type: str,
    *,
    tag_fn=tag_image,
) -> tuple[VisionCallResult, int]:
    """Retries only 429/5xx (transient). Any other exception, or exhausting
    all attempts, propagates to the caller. Returns (result, attempts_used)
    so the caller can log accurate per-call cost/attempt data even when a
    call only succeeded after a retry.
    """
    result: VisionCallResult | None = None
    attempts_used = 0
    async for attempt in AsyncRetrying(
        retry=retry_if_exception(_is_transient),
        stop=stop_after_attempt(_MAX_ATTEMPTS),
        wait=wait_exponential(multiplier=1, min=1, max=20),
        reraise=True,
    ):
        with attempt:
            attempts_used = attempt.retry_state.attempt_number
            result = await tag_fn(image_bytes, mime_type)
    assert result is not None
    return result, attempts_used


def _log_model_call(
    conn,
    *,
    kind: CallKind,
    model: str,
    input_units: int,
    output_units: int,
    cost_usd: float,
    ref_id: UUID,
    ok: bool,
    attempt: int,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            insert into model_calls
                (kind, model, input_units, output_units, cost_usd, ref_id, ok, attempt)
            values (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (kind.value, model, input_units, output_units, cost_usd, str(ref_id), ok, attempt),
        )


def _insert_ok_tag(conn, image_id: UUID, result: VisionCallResult, status: TagStatus) -> None:
    parsed = result.parsed
    assert parsed is not None
    with conn.cursor() as cur:
        cur.execute(
            """
            insert into image_tags
                (image_id, subject, category, attributes, caption, confidence, status, model)
            values (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                str(image_id),
                parsed.subject.value,
                parsed.category.value,
                parsed.attributes,
                parsed.caption,
                parsed.confidence,
                status.value,
                result.model_version,
            ),
        )


def _insert_invalid_tag(conn, image_id: UUID, model: str, reason: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            insert into image_tags
                (image_id, subject, category, attributes, caption, confidence, status, model)
            values (%s, null, null, null, %s, null, %s, %s)
            """,
            (str(image_id), reason[:300], TagStatus.INVALID_OUTPUT.value, model),
        )


@dataclass
class ClassifyOutcome:
    image_id: UUID
    status: TagStatus


async def _classify_one(semaphore: asyncio.Semaphore, image_id: UUID, source_uri: str) -> ClassifyOutcome:
    async with semaphore:
        try:
            image_bytes, mime_type = _load_image_bytes(source_uri)
        except OSError as exc:
            logger.warning("could not load image %s: %s", image_id, exc)
            with get_connection() as conn:
                _insert_invalid_tag(conn, image_id, settings.vision_model, f"could not load image: {exc}")
                conn.commit()
            return ClassifyOutcome(image_id, TagStatus.INVALID_OUTPUT)

        try:
            result, attempts_used = await _tag_with_retry(image_bytes, mime_type)
        except Exception as exc:
            attempts_used = _MAX_ATTEMPTS if _is_transient(exc) else 1
            logger.warning("vision call failed for %s after %d attempt(s): %s", image_id, attempts_used, exc)
            with get_connection() as conn:
                _log_model_call(
                    conn,
                    kind=CallKind.VISION,
                    model=settings.vision_model,
                    input_units=0,
                    output_units=0,
                    cost_usd=0.0,
                    ref_id=image_id,
                    ok=False,
                    attempt=attempts_used,
                )
                _insert_invalid_tag(conn, image_id, settings.vision_model, f"vision call failed: {exc}")
                conn.commit()
            return ClassifyOutcome(image_id, TagStatus.INVALID_OUTPUT)

        with get_connection() as conn:
            _log_model_call(
                conn,
                kind=CallKind.VISION,
                model=result.model_version,
                input_units=result.input_tokens,
                output_units=result.output_tokens,
                cost_usd=result.cost_usd,
                ref_id=image_id,
                ok=result.parsed is not None,
                attempt=attempts_used,
            )
            if result.parsed is None:
                _insert_invalid_tag(conn, image_id, result.model_version, result.error or "validation failed")
                status = TagStatus.INVALID_OUTPUT
            else:
                status = derive_status(result.parsed, settings.conf_floor)
                _insert_ok_tag(conn, image_id, result, status)
            conn.commit()

        logger.info("tagged %s -> %s", image_id, status.value)
        return ClassifyOutcome(image_id, status)


def _fetch_untagged_images(conn) -> list[tuple[UUID, str]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            select i.id, i.source_uri
            from images i
            left join image_tags t on t.image_id = i.id
            where t.image_id is null
            order by i.created_at
            """
        )
        return cur.fetchall()


async def run_classification_job(concurrency: int = 5) -> dict[str, int]:
    with get_connection() as conn:
        pending = _fetch_untagged_images(conn)

    logger.info("classifying %d untagged image(s)", len(pending))
    semaphore = asyncio.Semaphore(concurrency)
    outcomes = await asyncio.gather(
        *(_classify_one(semaphore, image_id, source_uri) for image_id, source_uri in pending)
    )

    summary: dict[str, int] = {}
    for outcome in outcomes:
        summary[outcome.status.value] = summary.get(outcome.status.value, 0) + 1
    logger.info("classification job done: %s", summary)
    return summary


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_classification_job())
