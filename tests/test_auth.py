"""Integration tests for /api/auth/* endpoints."""
import pytest
from fastapi.testclient import TestClient
from .conftest import register, auth_headers


def test_register_success(client: TestClient):
    data = register(client)
    assert data["user_id"]
    assert data["name"] == "Alice"
    assert data["email"] == "alice@test.com"
    assert data["access_token"]
    assert data["token_type"] == "bearer"
    assert data["theme"] == "dark"


def test_register_duplicate_email(client: TestClient):
    register(client)
    r = client.post("/api/auth/register", json={"name": "Alice2", "email": "alice@test.com", "password": "secret123"})
    assert r.status_code == 400
    assert "already registered" in r.json()["detail"]


def test_register_short_password(client: TestClient):
    r = client.post("/api/auth/register", json={"name": "Bob", "email": "bob@test.com", "password": "12"})
    assert r.status_code == 422


def test_login_success(client: TestClient):
    register(client)
    r = client.post("/api/auth/login", json={"email": "alice@test.com", "password": "secret123"})
    assert r.status_code == 200
    assert r.json()["access_token"]


def test_login_wrong_password(client: TestClient):
    register(client)
    r = client.post("/api/auth/login", json={"email": "alice@test.com", "password": "WRONG"})
    assert r.status_code == 401


def test_login_unknown_email(client: TestClient):
    r = client.post("/api/auth/login", json={"email": "ghost@test.com", "password": "anything"})
    assert r.status_code == 401


def test_get_me(client: TestClient):
    data = register(client)
    r = client.get("/api/auth/me", headers=auth_headers(data["access_token"]))
    assert r.status_code == 200
    assert r.json()["email"] == "alice@test.com"


def test_get_me_no_token(client: TestClient):
    r = client.get("/api/auth/me")
    assert r.status_code == 401


def test_pair_with_partner(client: TestClient):
    a = register(client, name="Alice", email="alice@test.com")
    b = register(client, name="Bob", email="bob@test.com")
    r = client.post(
        "/api/auth/pair",
        json={"partner_email": "bob@test.com"},
        headers=auth_headers(a["access_token"]),
    )
    assert r.status_code == 200
    assert r.json()["partner_id"] == b["user_id"]


def test_pair_self_fails(client: TestClient):
    a = register(client)
    r = client.post(
        "/api/auth/pair",
        json={"partner_email": "alice@test.com"},
        headers=auth_headers(a["access_token"]),
    )
    assert r.status_code == 400


def test_pair_unknown_email_fails(client: TestClient):
    a = register(client)
    r = client.post(
        "/api/auth/pair",
        json={"partner_email": "nobody@test.com"},
        headers=auth_headers(a["access_token"]),
    )
    assert r.status_code == 404


def test_invite_and_pair_by_token(client: TestClient):
    a = register(client, name="Alice", email="alice@test.com")
    b = register(client, name="Bob", email="bob@test.com")

    # Alice generates invite
    r = client.post("/api/auth/invite", headers=auth_headers(a["access_token"]))
    assert r.status_code == 200
    token = r.json()["token"]
    assert len(token) == 10
    assert "watchmatch.crig.dev" in r.json()["url"]

    # Bob uses token to pair
    r2 = client.post(
        "/api/auth/pair-by-token",
        json={"token": token},
        headers=auth_headers(b["access_token"]),
    )
    assert r2.status_code == 200
    assert r2.json()["partner_id"] == a["user_id"]

    # Token is invalidated — second use fails
    r3 = client.post(
        "/api/auth/pair-by-token",
        json={"token": token},
        headers=auth_headers(b["access_token"]),
    )
    assert r3.status_code == 404


def test_pair_by_invalid_token(client: TestClient):
    b = register(client, name="Bob", email="bob@test.com")
    r = client.post(
        "/api/auth/pair-by-token",
        json={"token": "doesnotexist"},
        headers=auth_headers(b["access_token"]),
    )
    assert r.status_code == 404


def test_update_theme(client: TestClient):
    a = register(client)
    r = client.patch(
        "/api/auth/me/theme",
        json={"theme": "light"},
        headers=auth_headers(a["access_token"]),
    )
    assert r.status_code == 200
    assert r.json()["theme"] == "light"


def test_delete_account(client: TestClient):
    a = register(client)
    r = client.request(
        "DELETE", "/api/auth/me",
        json={"password": "secret123"},
        headers=auth_headers(a["access_token"]),
    )
    assert r.status_code == 204

    # Token should no longer work
    r2 = client.get("/api/auth/me", headers=auth_headers(a["access_token"]))
    assert r2.status_code == 401


def test_delete_account_wrong_password(client: TestClient):
    a = register(client)
    r = client.request(
        "DELETE", "/api/auth/me",
        json={"password": "WRONG"},
        headers=auth_headers(a["access_token"]),
    )
    assert r.status_code == 401
