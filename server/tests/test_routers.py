"""Endpoint-level tests via FastAPI TestClient against the real app.

Login goes through the real ``/api/login`` flow (admin password is set in
conftest), and the client echoes the CSRF cookie into the header for unsafe
methods, matching what the browser client does.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from cataloguecanvas.main import app


@pytest.fixture()
def client():
    return TestClient(app)


def _csrf_headers(client: TestClient) -> dict:
    token = client.cookies.get("cc_csrf")
    return {"X-CSRF-Token": token} if token else {}


@pytest.fixture()
def admin(client):
    """A logged-in admin client (cookies persisted on the client)."""
    resp = client.post("/api/login", json={"password": "hunter2"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["role"] == "admin"
    return client


# --- auth flow ---

def test_me_anonymous(client):
    body = client.get("/api/me").json()
    assert body["authenticated"] is False
    assert body["role"] is None


def test_login_bad_password(client):
    resp = client.post("/api/login", json={"password": "wrong"})
    assert resp.status_code == 401


def test_me_after_login(admin):
    body = admin.get("/api/me").json()
    assert body["authenticated"] is True
    assert body["role"] == "admin"


def test_logout(admin):
    resp = admin.post("/api/logout", headers=_csrf_headers(admin))
    assert resp.status_code == 200


# --- auth required ---

def test_collections_requires_auth(client):
    assert client.get("/api/collections").status_code == 401


def test_settings_requires_admin(client):
    assert client.get("/api/settings").status_code == 401


# --- happy paths (admin) ---

def test_list_collections(admin):
    resp = admin.get("/api/collections")
    assert resp.status_code == 200
    # the seeded 'favorites' system collection should be present
    assert any(c["id"] == "favorites" for c in resp.json())


def test_get_settings(admin):
    body = admin.get("/api/settings").json()
    assert "llm_prompt_template" in body
    assert "stats" in body


def test_appearance_is_public(client):
    # appearance has no auth dependency
    resp = client.get("/api/settings/appearance")
    assert resp.status_code == 200
    assert resp.json()["theme"] in ("light", "dark")


def test_list_items(admin):
    resp = admin.get("/api/items")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_list_libraries(admin):
    resp = admin.get("/api/libraries")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_list_portfolios(admin):
    resp = admin.get("/api/portfolios")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_create_and_delete_collection(admin):
    created = admin.post(
        "/api/collections",
        json={"title": "Travel"},
        headers=_csrf_headers(admin),
    )
    assert created.status_code in (200, 201), created.text
    col_id = created.json()["id"]
    got = admin.get(f"/api/collections/{col_id}")
    assert got.status_code == 200
    deleted = admin.request(
        "DELETE", f"/api/collections/{col_id}", headers=_csrf_headers(admin)
    )
    assert deleted.status_code == 200


def test_get_missing_item_404(admin):
    assert admin.get("/api/items/does-not-exist").status_code == 404
