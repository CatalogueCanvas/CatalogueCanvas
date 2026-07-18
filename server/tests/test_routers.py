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
    # LLM response wait timeout has a default and is exposed.
    assert body["llm_timeout"] == "90"


def test_update_llm_timeout(admin):
    resp = admin.put("/api/settings", json={"llm_timeout": "240"}, headers=_csrf_headers(admin))
    assert resp.status_code == 200
    assert resp.json()["llm_timeout"] == "240"
    # persisted across a fresh read
    assert admin.get("/api/settings").json()["llm_timeout"] == "240"


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


def _make_public_portfolio(admin) -> dict:
    resp = admin.post(
        "/api/portfolios",
        json={"title": "Showcase", "is_public": True},
        headers=_csrf_headers(admin),
    )
    assert resp.status_code in (200, 201), resp.text
    return resp.json()


def test_public_portfolio_without_token(admin, client):
    """A public portfolio with no share token opens for anyone (regression)."""
    p = _make_public_portfolio(admin)
    # Use a fresh, unauthenticated client to confirm public access.
    from fastapi.testclient import TestClient
    from cataloguecanvas.main import app

    anon = TestClient(app)
    resp = anon.get(f"/api/p/{p['slug']}")
    assert resp.status_code == 200
    assert resp.json()["slug"] == p["slug"]


def test_share_token_gates_and_cookie_remembers(admin):
    p = _make_public_portfolio(admin)
    slug = p["slug"]

    minted = admin.post(
        f"/api/portfolios/{p['id']}/share-token", headers=_csrf_headers(admin)
    )
    assert minted.status_code == 200, minted.text
    token = minted.json()["share_token"]
    assert token

    from fastapi.testclient import TestClient
    from cataloguecanvas.main import app

    # No token in URL -> 404 (indistinguishable from missing).
    anon = TestClient(app)
    assert anon.get(f"/api/p/{slug}").status_code == 404

    # Wrong token -> 404.
    assert anon.get(f"/api/p/{slug}/wrong-token").status_code == 404

    # Correct token -> 200 and a share cookie is set.
    ok = anon.get(f"/api/p/{slug}/{token}")
    assert ok.status_code == 200
    # Cookie is keyed by the portfolio id (a safe hex string), not the slug.
    assert f"cc_share_{p['id']}" in anon.cookies

    # The cookie now lets the bare slug through on the same client.
    assert anon.get(f"/api/p/{slug}").status_code == 200


def test_clear_share_token_reopens(admin):
    p = _make_public_portfolio(admin)
    slug = p["slug"]
    admin.post(f"/api/portfolios/{p['id']}/share-token", headers=_csrf_headers(admin))

    from fastapi.testclient import TestClient
    from cataloguecanvas.main import app

    anon = TestClient(app)
    assert anon.get(f"/api/p/{slug}").status_code == 404

    cleared = admin.request(
        "DELETE", f"/api/portfolios/{p['id']}/share-token", headers=_csrf_headers(admin)
    )
    assert cleared.status_code == 200

    anon2 = TestClient(app)
    assert anon2.get(f"/api/p/{slug}").status_code == 200


# --- storage file path validation ---

def test_storage_file_requires_auth(client):
    """Storage endpoints require authentication."""
    resp = client.get("/storage/any-lib/any-file.txt")
    assert resp.status_code == 401


def test_storage_nonexistent_library_404(admin):
    """Requesting a file from a non-existent library returns 404."""
    resp = admin.get("/storage/no-such-lib/file.txt")
    assert resp.status_code == 404


def test_storage_relative_to_blocks_traversal(tmp_path):
    """relative_to() rejects resolved paths outside the library root."""
    lib_root = (tmp_path / "mylib").resolve()
    lib_root.mkdir()
    (lib_root / "safe.txt").write_text("ok")

    secret = tmp_path / "secret.txt"
    secret.write_text("secret")

    for rel in ["../secret.txt", "../../etc/passwd", "sub/../../secret.txt"]:
        target = (lib_root / rel).resolve()
        escaped = True
        try:
            target.relative_to(lib_root)
            escaped = False
        except ValueError:
            pass
        assert escaped, f"relative_to did not reject '{rel}'"


def test_storage_symlink_detected(tmp_path):
    """Symlinks inside the library root are detected."""
    lib_root = tmp_path / "lib"
    lib_root.mkdir()

    external = tmp_path / "external.txt"
    external.write_text("external")

    link = lib_root / "link.txt"
    try:
        link.symlink_to(external)
    except (OSError, NotImplementedError):
        return

    assert link.is_symlink()
    resolved = link.resolve()
    escaped = True
    try:
        resolved.relative_to(lib_root.resolve())
        escaped = False
    except ValueError:
        pass
    assert escaped, "Symlink target was not detected as outside library root"
