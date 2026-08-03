from uuid import uuid4

from guard import guard
from schemas import Candidate, GuardReason, Verdict
from vocab import Subject

SIM_FLOOR = 0.35
CONF_FLOOR = 0.6


def make_candidate(
    subject: Subject,
    similarity: float,
    tag_confidence: float = 0.9,
) -> Candidate:
    return Candidate(
        image_id=uuid4(),
        subject=subject,
        similarity=similarity,
        tag_confidence=tag_confidence,
    )


def test_wrong_top_hit_with_no_rescue_available_is_no_match():
    candidates = [
        make_candidate(Subject.GRAY_WOLF, 0.82),
        make_candidate(Subject.DOMESTIC_DOG, 0.60),
    ]
    decision = guard(Subject.RED_FOX, candidates, SIM_FLOOR, CONF_FLOOR)
    assert decision.verdict == Verdict.NO_MATCH
    assert decision.reason == GuardReason.SUBJECT_MISMATCH


def test_wrong_top_hit_rescues_fox_from_rank_three():
    fox = make_candidate(Subject.RED_FOX, 0.55)
    candidates = [
        make_candidate(Subject.GRAY_WOLF, 0.82),
        make_candidate(Subject.DOMESTIC_DOG, 0.60),
        fox,
    ]
    decision = guard(Subject.RED_FOX, candidates, SIM_FLOOR, CONF_FLOOR)
    assert decision.verdict == Verdict.SUGGEST
    assert decision.reason == GuardReason.PROMOTED_OVER_TOP_HIT
    assert decision.image_id == fox.image_id


def test_correct_top_hit_high_confidence_is_suggested():
    fox = make_candidate(Subject.RED_FOX, 0.78, tag_confidence=0.9)
    candidates = [fox, make_candidate(Subject.GRAY_WOLF, 0.60)]
    decision = guard(Subject.RED_FOX, candidates, SIM_FLOOR, CONF_FLOOR)
    assert decision.verdict == Verdict.SUGGEST
    assert decision.reason == GuardReason.OK
    assert decision.image_id == fox.image_id


def test_correct_top_hit_low_confidence_is_flagged():
    fox = make_candidate(Subject.RED_FOX, 0.78, tag_confidence=0.3)
    decision = guard(Subject.RED_FOX, [fox], SIM_FLOOR, CONF_FLOOR)
    assert decision.verdict == Verdict.FLAG
    assert decision.reason == GuardReason.LOW_TAG_CONFIDENCE
    assert decision.image_id == fox.image_id


def test_all_candidates_below_similarity_floor_is_no_match():
    candidates = [
        make_candidate(Subject.RED_FOX, 0.20),
        make_candidate(Subject.GRAY_WOLF, 0.10),
    ]
    decision = guard(Subject.RED_FOX, candidates, SIM_FLOOR, CONF_FLOOR)
    assert decision.verdict == Verdict.NO_MATCH
    assert decision.reason == GuardReason.BELOW_SIMILARITY_FLOOR


def test_unknown_top_hit_subject_is_not_suggested():
    candidates = [make_candidate(Subject.UNKNOWN, 0.80)]
    decision = guard(Subject.UNKNOWN, candidates, SIM_FLOOR, CONF_FLOOR)
    assert decision.verdict != Verdict.SUGGEST
    assert decision.reason == GuardReason.SUBJECT_UNKNOWN


def test_empty_candidate_list_is_no_match_without_crashing():
    decision = guard(Subject.RED_FOX, [], SIM_FLOOR, CONF_FLOOR)
    assert decision.verdict == Verdict.NO_MATCH
