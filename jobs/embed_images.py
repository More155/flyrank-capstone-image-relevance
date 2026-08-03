"""Batch caption embedding — the second half of Flow A's ingestion
(BRIEF.md §4): embed(caption) -> image_vectors, after jobs/classify.py has
already produced image_tags. Idempotent (skips images already embedded).
"""

from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from config import settings
from db import get_connection
from embeddings import embed_text
from schemas import CallKind

logger = logging.getLogger(__name__)


def _fetch_pending(conn) -> list[tuple[UUID, str]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            select t.image_id, t.caption
            from image_tags t
            left join image_vectors v on v.image_id = t.image_id
            where v.image_id is null and t.caption is not null
            order by t.created_at
            """
        )
        return cur.fetchall()


def _log_model_call(conn, *, model: str, input_units: int, cost_usd: float, ref_id: UUID, ok: bool) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            insert into model_calls
                (kind, model, input_units, output_units, cost_usd, ref_id, ok, attempt)
            values (%s, %s, %s, 0, %s, %s, %s, 1)
            """,
            (CallKind.EMBED_IMAGE.value, model, input_units, cost_usd, str(ref_id), ok),
        )


async def _embed_one(semaphore: asyncio.Semaphore, image_id: UUID, caption: str) -> bool:
    async with semaphore:
        try:
            result = await embed_text(caption)
        except Exception as exc:
            logger.warning("embedding failed for %s: %s", image_id, exc)
            with get_connection() as conn:
                _log_model_call(conn, model=settings.embedding_model, input_units=0, cost_usd=0.0, ref_id=image_id, ok=False)
                conn.commit()
            return False

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "insert into image_vectors (image_id, embedding, model) values (%s, %s, %s)",
                    (str(image_id), result.vector, result.model),
                )
            _log_model_call(
                conn,
                model=result.model,
                input_units=result.input_tokens,
                cost_usd=result.cost_usd,
                ref_id=image_id,
                ok=True,
            )
            conn.commit()

        logger.info("embedded %s", image_id)
        return True


async def run_embedding_job(concurrency: int = 5) -> dict[str, int]:
    with get_connection() as conn:
        pending = _fetch_pending(conn)

    logger.info("embedding %d image caption(s)", len(pending))
    semaphore = asyncio.Semaphore(concurrency)
    results = await asyncio.gather(*(_embed_one(semaphore, image_id, caption) for image_id, caption in pending))

    summary = {"ok": sum(results), "failed": len(results) - sum(results)}
    logger.info("embedding job done: %s", summary)
    return summary


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_embedding_job())
