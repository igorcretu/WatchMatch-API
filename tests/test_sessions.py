"""Integration tests for /api/sessions/* endpoints — including route ordering."""
import pytest
from fastapi.testclient import TestClient
from .conftest import register, auth_headers


def _create_session(client, token, partner_id=None, content_type="both"):
    r = client.post(
        "/api/sessions",
        json={"partner_id": partner_id, "content_type": content_type},
        headers=auth_headers(token),
    )
    assert r.status_code == 201, r.text
    return r.json()


# ---------- Session CRUD ----------

def test_create_session_solo(client: TestClient):
    a = register(client)
    sess = _create_session(client, a["access_token"])
    assert sess["id"]
    assert sess["user_id"] == a["user_id"]
    assert sess["partner_id"] is None
    assert sess["status"] == "waiting"
    assert sess["content_type"] == "both"


def test_create_session_with_partner(client: TestClient):
    a = register(client, name="Alice", email="alice@test.com")
    b = register(client, name="Bob", email="bob@test.com")
    sess = _create_session(client, a["access_token"], partner_id=b["user_id"])
    assert sess["partner_id"] == b["user_id"]


def test_create_session_content_type(client: TestClient):
    a = register(client)
    sess = _create_session(client, a["access_token"], content_type="movie")
    assert sess["content_type"] == "movie"


def test_get_session(client: TestClient):
    a = register(client)
    sess = _create_session(client, a["access_token"])
    r = client.get(f"/api/sessions/{sess['id']}", headers=auth_headers(a["access_token"]))
    assert r.status_code == 200
    assert r.json()["id"] == sess["id"]


def test_get_session_not_found(client: TestClient):
    a = register(client)
    r = client.get("/api/sessions/does-not-exist", headers=auth_headers(a["access_token"]))
    assert r.status_code == 404


def test_get_session_forbidden_for_non_participant(client: TestClient):
    a = register(client, name="Alice", email="alice@test.com")
    b = register(client, name="Bob", email="bob@test.com")
    sess = _create_session(client, a["access_token"])
    r = client.get(f"/api/sessions/{sess['id']}", headers=auth_headers(b["access_token"]))
    assert r.status_code == 403


# ---------- Filters ----------

def test_get_default_filters(client: TestClient):
    a = register(client)
    sess = _create_session(client, a["access_token"])
    r = client.get(f"/api/sessions/{sess['id']}/filters", headers=auth_headers(a["access_token"]))
    assert r.status_code == 200
    data = r.json()
    assert "genres" in data
    assert "providers" in data
    assert "moods" in data
    assert "year_min" in data
    assert "rating_min" in data


def test_update_filters_changes_status(client: TestClient):
    a = register(client)
    sess = _create_session(client, a["access_token"])
    filters = {
        "genres": [{"label": "Drama", "state": "must"}],
        "year_min": 2010, "year_max": 2024,
        "rating_min": 7.0, "runtime_max": 150,
        "providers": [{"label": "Netflix", "state": "nice"}],
        "moods": [{"label": "tense", "state": "nice"}],
    }
    r = client.patch(
        f"/api/sessions/{sess['id']}/filters",
        json=filters,
        headers=auth_headers(a["access_token"]),
    )
    assert r.status_code == 200
    assert r.json()["status"] == "active"


def test_filters_roundtrip(client: TestClient):
    a = register(client)
    sess = _create_session(client, a["access_token"])
    filters = {
        "genres": [{"label": "Sci-Fi", "state": "must"}, {"label": "Horror", "state": "no"}],
        "year_min": 2000, "year_max": 2023,
        "rating_min": 8.0, "runtime_max": 120,
        "providers": [{"label": "Max", "state": "must"}],
        "moods": [{"label": "cerebral", "state": "must"}],
    }
    client.patch(f"/api/sessions/{sess['id']}/filters", json=filters, headers=auth_headers(a["access_token"]))
    r = client.get(f"/api/sessions/{sess['id']}/filters", headers=auth_headers(a["access_token"]))
    assert r.status_code == 200
    data = r.json()
    sci_fi = next(g for g in data["genres"] if g["label"] == "Sci-Fi")
    assert sci_fi["state"] == "must"
    horror = next(g for g in data["genres"] if g["label"] == "Horror")
    assert horror["state"] == "no"


# ---------- Presets (critical: must resolve before /{session_id}) ----------

def test_presets_route_not_matched_as_session_id(client: TestClient):
    """GET /sessions/presets must NOT return 404 (session not found) — route ordering bug."""
    a = register(client)
    r = client.get("/api/sessions/presets", headers=auth_headers(a["access_token"]))
    assert r.status_code == 200  # returns [] not 404
    assert isinstance(r.json(), list)


def test_create_and_list_preset(client: TestClient):
    a = register(client)
    filters = {
        "genres": [{"label": "Drama", "state": "must"}],
        "year_min": 2015, "year_max": 2025,
        "rating_min": 7.0, "runtime_max": 120,
        "providers": [{"label": "Netflix", "state": "nice"}],
        "moods": [{"label": "cozy", "state": "nice"}],
    }
    r = client.post(
        "/api/sessions/presets",
        json={"name": "Date Night", "filters": filters},
        headers=auth_headers(a["access_token"]),
    )
    assert r.status_code == 201
    preset_id = r.json()["id"]

    r2 = client.get("/api/sessions/presets", headers=auth_headers(a["access_token"]))
    assert r2.status_code == 200
    names = [p["name"] for p in r2.json()]
    assert "Date Night" in names


def test_delete_preset(client: TestClient):
    a = register(client)
    filters = {
        "genres": [{"label": "Drama", "state": "nice"}],
        "year_min": 2015, "year_max": 2025,
        "rating_min": 6.5, "runtime_max": 180,
        "providers": [], "moods": [],
    }
    r = client.post(
        "/api/sessions/presets",
        json={"name": "TMP", "filters": filters},
        headers=auth_headers(a["access_token"]),
    )
    pid = r.json()["id"]
    r2 = client.delete(f"/api/sessions/presets/{pid}", headers=auth_headers(a["access_token"]))
    assert r2.status_code == 204

    r3 = client.get("/api/sessions/presets", headers=auth_headers(a["access_token"]))
    assert not any(p["id"] == pid for p in r3.json())


def test_preset_isolated_per_user(client: TestClient):
    a = register(client, name="Alice", email="alice@test.com")
    b = register(client, name="Bob", email="bob@test.com")
    filters = {
        "genres": [{"label": "Drama", "state": "nice"}],
        "year_min": 2015, "year_max": 2025,
        "rating_min": 6.5, "runtime_max": 180,
        "providers": [], "moods": [],
    }
    client.post(
        "/api/sessions/presets",
        json={"name": "Alice's preset", "filters": filters},
        headers=auth_headers(a["access_token"]),
    )
    r = client.get("/api/sessions/presets", headers=auth_headers(b["access_token"]))
    assert r.json() == []


# ---------- Session Replay ----------

def test_session_replay(client: TestClient):
    a = register(client)
    sess = _create_session(client, a["access_token"])
    client.post(
        f"/api/sessions/{sess['id']}/swipe",
        json={"movie_id": "m01", "action": "like"},
        headers=auth_headers(a["access_token"]),
    )
    r = client.get(f"/api/sessions/{sess['id']}/replay", headers=auth_headers(a["access_token"]))
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 1
    assert items[0]["movie_id"] == "m01"
    assert items[0]["action"] == "like"
    assert items[0]["movie_title"] == "Inception"
