"""The mismatch guard.

Two separate mechanisms, on purpose (see BRIEF.md section 1):
- similarity floor answers "is anything relevant at all?"
- canonical subject equality answers "is it the right animal?"

`candidates` must already be ranked by similarity, descending (that's the
matching step's job, not this one's).
"""

from __future__ import annotations

from schemas import Candidate, GuardDecision, GuardReason, Verdict
from vocab import Subject


def guard(
    post_subject: Subject,
    candidates: list[Candidate],
    sim_floor: float,
    conf_floor: float,
) -> GuardDecision:
    if not candidates:
        return GuardDecision(
            verdict=Verdict.NO_MATCH,
            reason=GuardReason.BELOW_SIMILARITY_FLOOR,
            explanation="no candidates",
        )

    best = candidates[0]

    # 1. no-match detection — is anything relevant at all?
    if best.similarity < sim_floor:
        return GuardDecision(
            verdict=Verdict.NO_MATCH,
            reason=GuardReason.BELOW_SIMILARITY_FLOOR,
            explanation=f"top candidate {best.similarity:.2f} below floor {sim_floor:.2f}",
        )

    # 2. wrong-match detection — is it the right animal?
    if best.subject != post_subject:
        rescue = next(
            (
                c
                for c in candidates
                if c.subject == post_subject and c.similarity >= sim_floor
            ),
            None,
        )
        if rescue is not None:
            return GuardDecision(
                verdict=Verdict.SUGGEST,
                reason=GuardReason.PROMOTED_OVER_TOP_HIT,
                explanation=(
                    f"top hit was {best.subject.value}; promoted "
                    f"{rescue.subject.value} at similarity {rescue.similarity:.2f}"
                ),
                image_id=rescue.image_id,
                similarity=rescue.similarity,
            )
        return GuardDecision(
            verdict=Verdict.NO_MATCH,
            reason=GuardReason.SUBJECT_MISMATCH,
            explanation=f"best is {best.subject.value}, post is {post_subject.value}",
        )

    # 3. trust check
    if best.subject is Subject.UNKNOWN:
        return GuardDecision(
            verdict=Verdict.NO_MATCH,
            reason=GuardReason.SUBJECT_UNKNOWN,
            explanation="top candidate subject is unknown",
        )
    if best.tag_confidence < conf_floor:
        return GuardDecision(
            verdict=Verdict.FLAG,
            reason=GuardReason.LOW_TAG_CONFIDENCE,
            explanation=f"tag confidence {best.tag_confidence:.2f} below floor {conf_floor:.2f}",
            image_id=best.image_id,
            similarity=best.similarity,
        )

    return GuardDecision(
        verdict=Verdict.SUGGEST,
        reason=GuardReason.OK,
        explanation=f"{best.subject.value} matched at similarity {best.similarity:.2f}",
        image_id=best.image_id,
        similarity=best.similarity,
    )
