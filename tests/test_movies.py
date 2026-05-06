"""Integration tests for /api/movies/* endpoints."""
import pytest
from fastapi.testclient import TestClient
from .conftest import register, auth_headers


def test_list_movies_requires_auth(client: TestClient):
    r = client.get("/api/movies")
    assert r.status_code == 401


def test_list_movies(client: TestClient):
    a = register(client)
    r = client.get("/api/movies", headers=auth_headers(a["access_token"]))
    assert r.status_code == 200
    movies = r.json()
    assert len(movies) == 16  # seeded fixture count
    # Verify shape of first movie
    m = movies[0]
    assert "id" in m
    assert "title" in m
    assert "genres" in m
    assert isinstance(m["genres"], list)
    assert "providers" in m
    assert isinstance(m["providers"], list)
    assert "content_type" in m
    assert "language" in m


def test_list_movies_year_filter(client: TestClient):
    a = register(client)
    r = client.get("/api/movies?year_min=2019&year_max=2019", headers=auth_headers(a["access_token"]))
    assert r.status_code == 200
    movies = r.json()
    assert all(m["year"] == 2019 for m in movies)
    assert len(movies) >= 2  # Parasite and Knives Out are 2019


def test_list_movies_rating_filter(client: TestClient):
    a = register(client)
    r = client.get("/api/movies?rating_min=8.5", headers=auth_headers(a["access_token"]))
    assert r.status_code == 200
    movies = r.json()
    assert all(m["rating"] >= 8.5 for m in movies)


def test_list_movies_runtime_filter(client: TestClient):
    a = register(client)
    r = client.get("/api/movies?runtime_max=110", headers=auth_headers(a["access_token"]))
    assert r.status_code == 200
    movies = r.json()
    assert all(m["runtime"] <= 110 for m in movies)


def test_list_movies_genre_must(client: TestClient):
    a = register(client)
    r = client.get("/api/movies?genres_must=Drama", headers=auth_headers(a["access_token"]))
    assert r.status_code == 200
    movies = r.json()
    assert all("Drama" in m["genres"] for m in movies)
    assert len(movies) > 0


def test_list_movies_genre_no(client: TestClient):
    a = register(client)
    r = client.get("/api/movies?genres_no=Horror", headers=auth_headers(a["access_token"]))
    assert r.status_code == 200
    movies = r.json()
    assert all("Horror" not in m["genres"] for m in movies)


def test_list_movies_provider_must(client: TestClient):
    a = register(client)
    r = client.get("/api/movies?providers_must=Netflix", headers=auth_headers(a["access_token"]))
    assert r.status_code == 200
    movies = r.json()
    assert all("Netflix" in m["providers"] for m in movies)


def test_list_movies_search(client: TestClient):
    a = register(client)
    r = client.get("/api/movies?q=inception", headers=auth_headers(a["access_token"]))
    assert r.status_code == 200
    movies = r.json()
    assert len(movies) == 1
    assert movies[0]["title"] == "Inception"


def test_list_movies_search_no_results(client: TestClient):
    a = register(client)
    r = client.get("/api/movies?q=zzznomatch", headers=auth_headers(a["access_token"]))
    assert r.status_code == 200
    assert r.json() == []


def test_get_movie(client: TestClient):
    a = register(client)
    r = client.get("/api/movies/m01", headers=auth_headers(a["access_token"]))
    assert r.status_code == 200
    assert r.json()["title"] == "Inception"


def test_get_movie_not_found(client: TestClient):
    a = register(client)
    r = client.get("/api/movies/m99", headers=auth_headers(a["access_token"]))
    assert r.status_code == 404


def test_hidden_movies_excluded(client: TestClient):
    a = register(client)
    hdrs = auth_headers(a["access_token"])

    # Create a session then hide movie m01
    sess = client.post("/api/sessions", json={"partner_id": None}, headers=hdrs).json()
    client.post(
        f"/api/sessions/{sess['id']}/swipe",
        json={"movie_id": "m01", "action": "hide"},
        headers=hdrs,
    )

    r = client.get("/api/movies", headers=hdrs)
    movie_ids = [m["id"] for m in r.json()]
    assert "m01" not in movie_ids
