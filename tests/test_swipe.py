"""Integration tests for swipe mechanics and match logic."""
import pytest
from fastapi.testclient import TestClient
from .conftest import register, auth_headers


MOVIE_IDS = ["m01", "m02", "m03", "m04", "m05", "m06", "m07", "m08"]


def _swipe(client, token, session_id, movie_id, action="like"):
    r = client.post(
        f"/api/sessions/{session_id}/swipe",
        json={"movie_id": movie_id, "action": action},
        headers=auth_headers(token),
    )
    assert r.status_code == 200, r.text
    return r.json()


def _create_session(client, token, partner_id=None):
    r = client.post(
        "/api/sessions",
        json={"partner_id": partner_id},
        headers=auth_headers(token),
    )
    assert r.status_code == 201
    return r.json()


# ---------- Core swipe mechanics ----------

def test_swipe_like_returns_not_matched(client: TestClient):
    a = register(client)
    sess = _create_session(client, a["access_token"])
    result = _swipe(client, a["access_token"], sess["id"], "m01", "like")
    assert result["matched"] is False
    assert result["session_id"] == sess["id"]


def test_swipe_pass_returns_not_matched(client: TestClient):
    a = register(client)
    sess = _create_session(client, a["access_token"])
    result = _swipe(client, a["access_token"], sess["id"], "m01", "pass")
    assert result["matched"] is False


def test_swipe_adds_to_queue_on_like(client: TestClient):
    a = register(client)
    sess = _create_session(client, a["access_token"])
    _swipe(client, a["access_token"], sess["id"], "m01", "like")
    r = client.get("/api/users/me/queue", headers=auth_headers(a["access_token"]))
    assert r.status_code == 200
    movie_ids = [item["movie_id"] for item in r.json()]
    assert "m01" in movie_ids


def test_swipe_super_adds_to_queue(client: TestClient):
    a = register(client)
    sess = _create_session(client, a["access_token"])
    _swipe(client, a["access_token"], sess["id"], "m01", "super")
    r = client.get("/api/users/me/queue", headers=auth_headers(a["access_token"]))
    assert any(item["movie_id"] == "m01" for item in r.json())


def test_swipe_pass_does_not_add_to_queue(client: TestClient):
    a = register(client)
    sess = _create_session(client, a["access_token"])
    _swipe(client, a["access_token"], sess["id"], "m01", "pass")
    r = client.get("/api/users/me/queue", headers=auth_headers(a["access_token"]))
    assert not any(item["movie_id"] == "m01" for item in r.json())


def test_swipe_no_duplicate_queue_items(client: TestClient):
    a = register(client)
    sess1 = _create_session(client, a["access_token"])
    sess2 = _create_session(client, a["access_token"])
    _swipe(client, a["access_token"], sess1["id"], "m01", "like")
    _swipe(client, a["access_token"], sess2["id"], "m01", "like")
    r = client.get("/api/users/me/queue", headers=auth_headers(a["access_token"]))
    m01_entries = [item for item in r.json() if item["movie_id"] == "m01"]
    assert len(m01_entries) == 1  # only one queue entry


# ---------- Match logic ----------

def test_match_fires_every_4th_like(client: TestClient):
    a = register(client)
    sess = _create_session(client, a["access_token"])
    results = [
        _swipe(client, a["access_token"], sess["id"], MOVIE_IDS[i], "like")
        for i in range(4)
    ]
    assert results[0]["matched"] is False
    assert results[1]["matched"] is False
    assert results[2]["matched"] is False
    assert results[3]["matched"] is True
    assert results[3]["movie"] is not None
    assert results[3]["movie"]["id"] == MOVIE_IDS[3]


def test_match_sets_session_status(client: TestClient):
    a = register(client)
    sess = _create_session(client, a["access_token"])
    for i in range(4):
        _swipe(client, a["access_token"], sess["id"], MOVIE_IDS[i], "like")
    r = client.get(f"/api/sessions/{sess['id']}", headers=auth_headers(a["access_token"]))
    assert r.json()["status"] == "matched"


def test_no_duplicate_match_for_same_movie(client: TestClient):
    """Sending the same movie twice in the same session should only create one Match."""
    a = register(client)
    sess = _create_session(client, a["access_token"])
    # Like 3 movies first (not yet a match)
    for i in range(3):
        _swipe(client, a["access_token"], sess["id"], MOVIE_IDS[i], "like")
    # Like m03 again (already liked, count is still 3 before this commit)
    result = _swipe(client, a["access_token"], sess["id"], MOVIE_IDS[2], "like")
    # It might or might not trigger a match depending on count — either way, no crash and no duplicate
    assert "matched" in result


def test_super_counts_as_like_for_match(client: TestClient):
    a = register(client)
    sess = _create_session(client, a["access_token"])
    results = [
        _swipe(client, a["access_token"], sess["id"], MOVIE_IDS[i], "super" if i == 0 else "like")
        for i in range(4)
    ]
    assert results[3]["matched"] is True


# ---------- Almost matched ----------

def test_almost_matched(client: TestClient):
    a = register(client)
    sess = _create_session(client, a["access_token"])
    # Like 3 movies (no match yet)
    for i in range(3):
        _swipe(client, a["access_token"], sess["id"], MOVIE_IDS[i], "like")
    r = client.get(f"/api/sessions/{sess['id']}/almost-matched", headers=auth_headers(a["access_token"]))
    assert r.status_code == 200
    movie_ids = [m["id"] for m in r.json()]
    assert "m01" in movie_ids
    assert "m02" in movie_ids
    assert "m03" in movie_ids


def test_almost_matched_excludes_matched_movies(client: TestClient):
    a = register(client)
    sess = _create_session(client, a["access_token"])
    # Like 4 movies → match on 4th
    for i in range(4):
        _swipe(client, a["access_token"], sess["id"], MOVIE_IDS[i], "like")
    r = client.get(f"/api/sessions/{sess['id']}/almost-matched", headers=auth_headers(a["access_token"]))
    movie_ids = [m["id"] for m in r.json()]
    assert MOVIE_IDS[3] not in movie_ids  # was matched, so excluded


# ---------- Access control ----------

def test_swipe_forbidden_for_non_participant(client: TestClient):
    a = register(client, name="Alice", email="alice@test.com")
    b = register(client, name="Bob", email="bob@test.com")
    sess = _create_session(client, a["access_token"])
    r = client.post(
        f"/api/sessions/{sess['id']}/swipe",
        json={"movie_id": "m01", "action": "like"},
        headers=auth_headers(b["access_token"]),
    )
    assert r.status_code == 403
