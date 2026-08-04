"""API-level tests that don't touch the live DB (this suite never does —
see tests/test_classify.py, test_vision.py, etc.). Endpoints that need a
real post/pairing/image are verified live instead: scripts/verify_matching.py
and EVIDENCE.md.
"""

from fastapi.testclient import TestClient

from api import app

client = TestClient(app)


def test_malformed_post_id_is_a_clean_422_not_a_500():
    resp = client.get("/posts/not-a-uuid/images")
    assert resp.status_code == 422


def test_malformed_pairing_id_is_a_clean_422_not_a_500():
    resp = client.post("/pairings/not-a-uuid/review", json={"action": "approved"})
    assert resp.status_code == 422


def test_review_action_rejects_unknown_action_value():
    resp = client.post(
        "/pairings/00000000-0000-0000-0000-000000000000/review",
        json={"action": "not-a-real-status"},
    )
    assert resp.status_code == 422
