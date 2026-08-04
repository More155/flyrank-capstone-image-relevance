"""Pairings: turns a GuardDecision into a stored, reviewable row (BRIEF.md
§4's Flow B — "Review API: approve / reject" — and the source brief's
"inspect why an image was selected or refused").
"""

from __future__ import annotations

from uuid import UUID

from db import get_connection
from matching import match_forced_image, match_images_for_post
from schemas import GuardDecision, PairingStatus, Verdict

#: What a human reviewer is allowed to set. SUGGESTED/REFUSED_BY_GUARD are
#: system-only outcomes of running the guard, never a review action.
REVIEWABLE_STATUSES = {PairingStatus.APPROVED, PairingStatus.REJECTED}


def _status_for_verdict(verdict: Verdict) -> PairingStatus:
    if verdict == Verdict.NO_MATCH:
        return PairingStatus.REFUSED_BY_GUARD
    return PairingStatus.SUGGESTED


def _insert_pairing(post_id: UUID, decision: GuardDecision) -> UUID:
    status = _status_for_verdict(decision.verdict)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into pairings
                    (post_id, image_id, similarity, verdict, reason, explanation, status)
                values (%s, %s, %s, %s, %s, %s, %s)
                returning id
                """,
                (
                    str(post_id),
                    str(decision.image_id) if decision.image_id else None,
                    decision.similarity,
                    decision.verdict.value,
                    decision.reason.value,
                    decision.explanation,
                    status.value,
                ),
            )
            (pairing_id,) = cur.fetchone()
        conn.commit()
    return pairing_id


async def create_pairing(post_id: UUID, force_image_id: UUID | None = None) -> tuple[UUID, GuardDecision]:
    """Runs the guard (natural ranking, or a forced candidate if
    force_image_id is given) and persists the result as a new pairing.
    """
    decision = (
        await match_forced_image(post_id, force_image_id)
        if force_image_id is not None
        else await match_images_for_post(post_id)
    )
    pairing_id = _insert_pairing(post_id, decision)
    return pairing_id, decision


def review_pairing(pairing_id: UUID, action: PairingStatus, note: str | None) -> None:
    if action not in REVIEWABLE_STATUSES:
        raise ValueError(f"{action.value!r} is not a valid review action — use approved or rejected")
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "update pairings set status = %s, note = %s where id = %s",
                (action.value, note, str(pairing_id)),
            )
            updated = cur.rowcount
        conn.commit()
    if updated == 0:
        raise ValueError(f"no pairing with id {pairing_id}")


def list_pairings_for_review() -> list[dict]:
    """One row per pairing, newest first, joined with post title and the
    suggested image's public URL (Unsplash — safe to hotlink directly as
    a thumbnail, no local storage needed).
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select p.id, p.post_id, po.title, p.image_id, i.source_uri,
                       p.similarity, p.verdict, p.reason, p.explanation,
                       p.status, p.note, p.created_at
                from pairings p
                join posts po on po.id = p.post_id
                left join images i on i.id = p.image_id
                order by p.created_at desc
                """
            )
            columns = [desc.name for desc in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]
