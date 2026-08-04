import pytest

from pairings import REVIEWABLE_STATUSES, _status_for_verdict
from schemas import PairingStatus, Verdict


@pytest.mark.parametrize(
    "verdict,expected",
    [
        (Verdict.SUGGEST, PairingStatus.SUGGESTED),
        (Verdict.FLAG, PairingStatus.SUGGESTED),
        (Verdict.NO_MATCH, PairingStatus.REFUSED_BY_GUARD),
    ],
)
def test_status_for_verdict(verdict, expected):
    assert _status_for_verdict(verdict) == expected


def test_reviewable_statuses_are_exactly_approve_and_reject():
    assert REVIEWABLE_STATUSES == {PairingStatus.APPROVED, PairingStatus.REJECTED}
