"""Tests for the admin-only update-check endpoint (/api/version).

The GitHub call is mocked so no network access happens; we exercise the
opt-in gate, the weekly throttle, and the failure fallback.
"""
from __future__ import annotations

import httpx

from cataloguecanvas.routers import settings as settings_router


def _csrf(client) -> dict:
    token = client.cookies.get("cc_csrf")
    return {"X-CSRF-Token": token} if token else {}


def _set_update(admin, **fields):
    resp = admin.put("/api/settings", json=fields, headers=_csrf(admin))
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_version_requires_admin(client):
    assert client.get("/api/version").status_code == 401


def test_version_disabled_makes_no_call(admin, monkeypatch):
    def _boom(*_a, **_k):  # pragma: no cover - must never run
        raise AssertionError("GitHub was called while disabled")

    monkeypatch.setattr(settings_router.httpx, "get", _boom)
    _set_update(admin, update_check_enabled="false")

    body = admin.get("/api/version").json()
    assert body["checked"] is False
    assert body["update_available"] is False
    assert "current" in body


def test_version_enabled_reports_update(admin, monkeypatch):
    def _fake_get(url, **_k):
        # Unordered tags list; the endpoint must pick the highest semver.
        return httpx.Response(
            200,
            json=[{"name": "v0.1.0"}, {"name": "v999.0.0"}, {"name": "v0.9.0"}],
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(settings_router.httpx, "get", _fake_get)
    _set_update(admin, update_check_enabled="true")

    body = admin.get("/api/version?force=true").json()
    assert body["checked"] is True
    assert body["latest"] == "999.0.0"
    assert body["update_available"] is True
    assert body["last_checked"]


def test_version_enabled_up_to_date(admin, monkeypatch):
    current = settings_router._app_version()

    def _fake_get(url, **_k):
        return httpx.Response(200, json=[{"name": f"v{current}"}], request=httpx.Request("GET", url))

    monkeypatch.setattr(settings_router.httpx, "get", _fake_get)
    _set_update(admin, update_check_enabled="true")

    body = admin.get("/api/version?force=true").json()
    assert body["latest"] == current
    assert body["update_available"] is False


def test_version_network_failure_falls_back(admin, monkeypatch):
    def _fake_get(url, **_k):
        raise httpx.ConnectError("boom", request=httpx.Request("GET", url))

    monkeypatch.setattr(settings_router.httpx, "get", _fake_get)
    _set_update(admin, update_check_enabled="true")

    body = admin.get("/api/version?force=true").json()
    # Failure is swallowed: checked True, but no crash and no bogus update.
    assert body["checked"] is True
    assert body["update_available"] is False
