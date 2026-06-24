"""Shared fixtures.

The app's ``settings`` object reads environment variables at import time, so we
must point CC_* at a throwaway data dir *before* any cataloguecanvas module is
imported. We do that here at collection time (module import), which runs before
the test modules import the app packages.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

# --- configure the app environment before importing any app module ---
_TMP_ROOT = Path(tempfile.mkdtemp(prefix="cc-tests-"))
os.environ.setdefault("CC_DATA_DIR", str(_TMP_ROOT / "data"))
os.environ.setdefault("CC_DB_PATH", str(_TMP_ROOT / "data" / "catalogue.db"))
os.environ.setdefault("CC_STORAGE_DIR", str(_TMP_ROOT / "storage"))
os.environ.setdefault("CC_SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("CC_ADMIN_PASSWORD", "hunter2")
os.environ.setdefault("CC_COOKIE_SECURE", "false")

from cataloguecanvas import db  # noqa: E402
from cataloguecanvas.settings import settings  # noqa: E402


@pytest.fixture()
def conn(tmp_path):
    """A fresh, schema-applied SQLite connection backed by a per-test file."""
    db_path = tmp_path / "test.db"
    connection = db.get_connection(db_path)
    db.ensure_schema(connection)
    try:
        yield connection
    finally:
        connection.close()


@pytest.fixture()
def app_conn():
    """A schema-applied connection on the *global* settings db_path.

    Endpoint tests run against the real app, which opens its own connections via
    ``settings.db_path``; seed data through this fixture so the app sees it.
    """
    connection = db.get_connection(settings.db_path)
    db.ensure_schema(connection)
    try:
        yield connection
    finally:
        connection.close()


@pytest.fixture()
def client():
    """FastAPI TestClient against the real app (cookies persist on the client)."""
    from fastapi.testclient import TestClient
    from cataloguecanvas.main import app

    return TestClient(app)


def csrf_headers(client) -> dict:
    """Echo the cc_csrf cookie into the header, as the browser client does."""
    token = client.cookies.get("cc_csrf")
    return {"X-CSRF-Token": token} if token else {}


@pytest.fixture()
def admin(client):
    """A logged-in admin TestClient."""
    resp = client.post("/api/login", json={"password": "hunter2"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["role"] == "admin"
    return client
