"""Flow B — matching (BRIEF.md §4). Online, per-request, no model calls on
the hot path except the one-time (then cached) post embedding.

Builds guard.py's inputs; does not touch guard.py's logic (per the Step 4
brief instruction) — rank_images_for_post produces a `Candidate` list
already sorted by similarity descending, guard() decides what to do with it.
"""

from __future__ import annotations

from uuid import UUID

from config import settings
from db import get_connection
from embeddings import embed_text
from guard import guard
from schemas import Candidate, GuardDecision
from vocab import Subject


async def ensure_post_embedded(post_id: UUID) -> None:
    """Embeds and caches a post's vector on first use. No-op if already
    embedded — "once, cached" per BRIEF.md's Flow B pseudocode.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("select 1 from post_vectors where post_id = %s", (str(post_id),))
            if cur.fetchone():
                return

            cur.execute("select title, body from posts where id = %s", (str(post_id),))
            row = cur.fetchone()
            if row is None:
                raise ValueError(f"no post with id {post_id}")
            title, body = row

        result = await embed_text(f"{title}\n\n{body}")

        with conn.cursor() as cur:
            cur.execute(
                "insert into post_vectors (post_id, embedding, model) values (%s, %s, %s)",
                (str(post_id), result.vector, result.model),
            )
        conn.commit()


def rank_images_for_post(post_id: UUID, top_k: int = 10) -> list[Candidate]:
    """pgvector top-k over image_vectors, joined with image_tags for the
    subject/confidence/caption the guard needs. Already sorted by
    similarity descending — the guard relies on that ordering.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("select embedding from post_vectors where post_id = %s", (str(post_id),))
            row = cur.fetchone()
            if row is None:
                raise ValueError(f"post {post_id} has no embedding — call ensure_post_embedded first")
            (post_embedding,) = row

            cur.execute(
                """
                select i.id, t.subject, t.confidence, t.caption,
                       1 - (v.embedding <=> %s) as similarity
                from image_vectors v
                join images i on i.id = v.image_id
                join image_tags t on t.image_id = v.image_id
                where t.subject is not null
                order by v.embedding <=> %s
                limit %s
                """,
                (post_embedding, post_embedding, top_k),
            )
            rows = cur.fetchall()

    return [
        Candidate(
            image_id=image_id,
            subject=Subject(subject),
            similarity=similarity,
            tag_confidence=confidence if confidence is not None else 0.0,
            caption=caption or "",
        )
        for image_id, subject, confidence, caption, similarity in rows
    ]


async def match_images_for_post(
    post_id: UUID,
    top_k: int = 10,
    sim_floor: float | None = None,
    conf_floor: float | None = None,
) -> GuardDecision:
    """The full Flow B pipeline: embed (if needed) -> rank -> guard."""
    await ensure_post_embedded(post_id)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("select subject from posts where id = %s", (str(post_id),))
            row = cur.fetchone()
            if row is None:
                raise ValueError(f"no post with id {post_id}")
            (post_subject,) = row

    candidates = rank_images_for_post(post_id, top_k=top_k)
    return guard(
        Subject(post_subject),
        candidates,
        sim_floor if sim_floor is not None else settings.sim_floor,
        conf_floor if conf_floor is not None else settings.conf_floor,
    )
