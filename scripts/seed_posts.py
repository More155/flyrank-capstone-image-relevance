"""Seeds the `posts` table from posts_seed.py, extracting each post's
subject via Gemini (extraction.extract_subject) and logging the cost.
Idempotent on title.
"""

from __future__ import annotations

import asyncio
import logging

from db import get_connection
from extraction import extract_subject
from posts_seed import POSTS
from schemas import CallKind

logger = logging.getLogger(__name__)


def _log_model_call(conn, *, model: str, input_units: int, output_units: int,
                     cost_usd: float, ref_id, ok: bool) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            insert into model_calls
                (kind, model, input_units, output_units, cost_usd, ref_id, ok, attempt)
            values (%s, %s, %s, %s, %s, %s, %s, 1)
            """,
            (CallKind.EXTRACT_SUBJECT.value, model, input_units, output_units, cost_usd, ref_id, ok),
        )


async def seed() -> dict[str, int]:
    counts = {"inserted": 0, "skipped": 0, "failed": 0}
    for post in POSTS:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("select 1 from posts where title = %s", (post.title,))
                if cur.fetchone():
                    counts["skipped"] += 1
                    continue

        try:
            result = await extract_subject(post.title, post.body)
        except Exception as exc:
            logger.warning("subject extraction failed for %r: %s", post.title, exc)
            counts["failed"] += 1
            continue

        if result.parsed is None:
            logger.warning("subject extraction returned invalid output for %r: %s", post.title, result.error)
            counts["failed"] += 1
            continue

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into posts (title, body, subject, subject_confidence)
                    values (%s, %s, %s, %s)
                    returning id
                    """,
                    (post.title, post.body, result.parsed.subject.value, result.parsed.confidence),
                )
                (post_id,) = cur.fetchone()
                _log_model_call(
                    conn,
                    model=result.model_version,
                    input_units=result.input_tokens,
                    output_units=result.output_tokens,
                    cost_usd=result.cost_usd,
                    ref_id=post_id,
                    ok=True,
                )
            conn.commit()
        counts["inserted"] += 1
        logger.info("seeded post %r -> %s (%.2f)", post.title, result.parsed.subject.value, result.parsed.confidence)

    logger.info("seed_posts: %s", counts)
    return counts


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(asyncio.run(seed()))
