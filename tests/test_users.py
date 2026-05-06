"""Integration tests for /api/users/* endpoints."""
import pytest
from fastapi.testclient import TestClient
from .conftest import register, auth_headers


def _create_session(client, token):
    r = client.post("/api/sessions", json={"partner_id": None}, headers=auth_headers(token))
    assert r.status_code == 201
    return r.json()


def _like(client, token, session_id, movie_id):
    r = client.post(
        f"/api/sessions/{session_id}/swipe",
        json={"movie_id": movie_id, "action": "like"},
        headers=auth_headers(token),
    )
    assert r.status_code == 200


def _pass(client, token, session_id, movie_id):
    r = client.post(
        f"/api/sessions/{session_id}/swipe",
        json={"movie_id": movie_id, "action": "pass"},
        headers=auth_headers(token),
    )
    assert r.status_code == 200


# ---------- Queue ----------

def test_queue_empty_by_default(client: TestClient):
    a = register(client)
    r = client.get("/api/users/me/queue", headers=auth_headers(a["access_token"]))
    assert r.status_code == 200
    assert r.json() == []


def test_queue_has_liked_movie(client: TestClient):
    a = register(client)
    sess = _create_session(client, a["access_token"])
    _like(client, a["access_token"], sess["id"], "m01")
    r = client.get("/api/users/me/queue", headers=auth_headers(a["access_token"]))
    assert len(r.json()) == 1
    item = r.json()[0]
    assert item["movie_id"] == "m01"
    assert item["watched"] is False
    assert item["movie"]["title"] == "Inception"
    assert "poster_path" in item["movie"]
    assert "rating" in item


def test_mark_watched(client: TestClient):
    a = register(client)
    sess = _create_session(client, a["access_token"])
    _like(client, a["access_token"], sess["id"], "m01")
    r = client.patch("/api/users/me/queue/m01/watched", headers=auth_headers(a["access_token"]))
    assert r.status_code == 200
    assert r.json()["watched"] is True


def test_watched_moves_to_history(client: TestClient):
    a = register(client)
    sess = _create_session(client, a["access_token"])
    _like(client, a["access_token"], sess["id"], "m01")
    client.patch("/api/users/me/queue/m01/watched", headers=auth_headers(a["access_token"]))

    # Queue should be empty
    queue = client.get("/api/users/me/queue", headers=auth_headers(a["access_token"])).json()
    assert not any(i["movie_id"] == "m01" for i in queue)

    # History should have it
    history = client.get("/api/users/me/history", headers=auth_headers(a["access_token"])).json()
    assert any(i["movie_id"] == "m01" for i in history)


def test_mark_watched_not_found(client: TestClient):
    a = register(client)
    r = client.patch("/api/users/me/queue/m99/watched", headers=auth_headers(a["access_token"]))
    assert r.status_code == 404


def test_queue_reorder(client: TestClient):
    a = register(client)
    sess = _create_session(client, a["access_token"])
    _like(client, a["access_token"], sess["id"], "m01")
    r = client.patch(
        "/api/users/me/queue/m01/reorder",
        json={"sort_order": 5},
        headers=auth_headers(a["access_token"]),
    )
    assert r.status_code == 200
    assert r.json()["sort_order"] == 5


# ---------- History & Ratings ----------

def test_history_empty_by_default(client: TestClient):
    a = register(client)
    r = client.get("/api/users/me/history", headers=auth_headers(a["access_token"]))
    assert r.status_code == 200
    assert r.json() == []


def test_rate_watched_movie(client: TestClient):
    a = register(client)
    hdrs = auth_headers(a["access_token"])
    sess = _create_session(client, a["access_token"])
    # Like 4 movies to trigger a match
    for mid in ["m01", "m02", "m03", "m04"]:
        _like(client, a["access_token"], sess["id"], mid)
    # Mark matched movie as watched
    client.patch("/api/users/me/queue/m04/watched", headers=hdrs)
    # Rate it
    r = client.patch("/api/users/me/history/m04/rate", json={"rating": 4}, headers=hdrs)
    assert r.status_code == 200


def test_rate_invalid_value(client: TestClient):
    a = register(client)
    hdrs = auth_headers(a["access_token"])
    sess = _create_session(client, a["access_token"])
    _like(client, a["access_token"], sess["id"], "m01")
    client.patch("/api/users/me/queue/m01/watched", headers=hdrs)
    r = client.patch("/api/users/me/history/m01/rate", json={"rating": 6}, headers=hdrs)
    assert r.status_code == 422


def test_rate_not_in_history(client: TestClient):
    a = register(client)
    r = client.patch(
        "/api/users/me/history/m99/rate",
        json={"rating": 3},
        headers=auth_headers(a["access_token"]),
    )
    assert r.status_code == 404


# ---------- Disliked ----------

def test_disliked_list(client: TestClient):
    a = register(client)
    sess = _create_session(client, a["access_token"])
    _pass(client, a["access_token"], sess["id"], "m01")
    r = client.get("/api/users/me/disliked", headers=auth_headers(a["access_token"]))
    assert r.status_code == 200
    assert any(m["id"] == "m01" for m in r.json())


def test_undo_dislike(client: TestClient):
    a = register(client)
    sess = _create_session(client, a["access_token"])
    _pass(client, a["access_token"], sess["id"], "m01")
    r = client.delete("/api/users/me/disliked/m01", headers=auth_headers(a["access_token"]))
    assert r.status_code == 204
    disliked = client.get("/api/users/me/disliked", headers=auth_headers(a["access_token"])).json()
    assert not any(m["id"] == "m01" for m in disliked)


# ---------- Stats ----------

def test_stats_empty(client: TestClient):
    a = register(client)
    r = client.get("/api/users/me/stats", headers=auth_headers(a["access_token"]))
    assert r.status_code == 200
    data = r.json()
    assert data["liked_count"] == 0
    assert data["watched_count"] == 0
    assert data["total_swipes"] == 0
    assert data["match_count"] == 0
    assert data["top_genres"] == []
    assert data["agreement_rate"] is None


def test_stats_after_likes(client: TestClient):
    a = register(client)
    sess = _create_session(client, a["access_token"])
    for mid in ["m01", "m02", "m03"]:
        _like(client, a["access_token"], sess["id"], mid)

    r = client.get("/api/users/me/stats", headers=auth_headers(a["access_token"]))
    data = r.json()
    assert data["liked_count"] == 3
    assert data["total_swipes"] == 3
    assert len(data["top_genres"]) > 0


def test_stats_match_count(client: TestClient):
    a = register(client)
    sess = _create_session(client, a["access_token"])
    for mid in ["m01", "m02", "m03", "m04"]:
        _like(client, a["access_token"], sess["id"], mid)

    r = client.get("/api/users/me/stats", headers=auth_headers(a["access_token"]))
    data = r.json()
    assert data["match_count"] == 1
    assert data["agreement_rate"] is not None


# ---------- Export ----------

def test_export_csv(client: TestClient):
    a = register(client)
    sess = _create_session(client, a["access_token"])
    _like(client, a["access_token"], sess["id"], "m01")
    r = client.get("/api/users/me/export", headers=auth_headers(a["access_token"]))
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    text = r.text
    assert "Inception" in text
    assert "title" in text  # header row


# ---------- Get user by ID ----------

def test_get_user_by_id(client: TestClient):
    a = register(client)
    r = client.get(f"/api/users/{a['user_id']}", headers=auth_headers(a["access_token"]))
    assert r.status_code == 200
    assert r.json()["name"] == "Alice"


def test_get_user_not_found(client: TestClient):
    a = register(client)
    r = client.get("/api/users/does-not-exist", headers=auth_headers(a["access_token"]))
    assert r.status_code == 404
