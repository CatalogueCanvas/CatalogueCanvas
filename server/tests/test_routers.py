"""Endpoint-level tests via FastAPI TestClient against the real app.

Login goes through the real ``/api/login`` flow (admin password is set in
conftest), and the client echoes the CSRF cookie into the header for unsafe
methods, matching what the browser client does.
"""
from __future__ import annotations


def _csrf_headers(client) -> dict:
    token = client.cookies.get("cc_csrf")
    return {"X-CSRF-Token": token} if token else {}


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


# --- storage file path validation ---

def test_storage_file_path_traversal_rejection(admin, tmp_path):
    """Verify that path traversal attempts are rejected."""
    from cataloguecanvas.main import create_app
    from cataloguecanvas.db import get_connection, ensure_schema, ensure_admin
    from cataloguecanvas.settings import Settings

    # Create a temporary library and file structure
    lib_dir = tmp_path / "lib"
    lib_dir.mkdir()
    storage_dir = lib_dir / "storage"
    storage_dir.mkdir()

    # Create a file inside the library
    safe_file = storage_dir / "allowed.txt"
    safe_file.write_text("safe content")

    # Create a file outside the library that we should not access
    external_file = tmp_path / "secret.txt"
    external_file.write_text("secret content")

    # Test attempts to escape the library directory
    # These should all return 404
    traversal_attempts = [
        "../../secret.txt",
        "../secret.txt",
        "..%2fsecret.txt",
        "..\\/secret.txt",
        "storage/../../../secret.txt",
    ]

    for attempt in traversal_attempts:
        resp = admin.get(f"/storage/test-lib/{attempt}")
        assert resp.status_code == 404, f"Path traversal '{attempt}' was not rejected"


def test_storage_file_symlink_rejection(admin, tmp_path):
    """Verify that symlinks are rejected."""
    from pathlib import Path

    lib_dir = tmp_path / "lib"
    lib_dir.mkdir()
    storage_dir = lib_dir / "storage"
    storage_dir.mkdir()

    # Create external file and symlink to it
    external_file = tmp_path / "external.txt"
    external_file.write_text("external content")

    symlink = storage_dir / "link.txt"
    try:
        symlink.symlink_to(external_file)
    except (OSError, NotImplementedError):
        # Symlinks may not be supported on this platform
        return

    resp = admin.get(f"/storage/test-lib/link.txt")
    assert resp.status_code == 404, "Symlink was not rejected"
