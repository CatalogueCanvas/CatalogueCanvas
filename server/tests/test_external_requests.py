"""Tests for the CC_ALLOW_EXTERNAL_REQUESTS guard.

The client address is what the middleware keys on, so these build requests with
an explicit peer rather than going through TestClient's synthetic "testclient"
host (which conftest opts out of globally).
"""
from __future__ import annotations

import pytest

from cataloguecanvas.main import ExternalRequestMiddleware, _is_private_address
from cataloguecanvas.settings import settings


@pytest.mark.parametrize("host", [
    "127.0.0.1",
    "::1",
    "192.168.1.20",
    "10.0.0.5",
    "172.16.4.9",
    "169.254.10.1",   # link-local
    "fc00::1",        # unique local
])
def test_private_addresses_allowed(host):
    assert _is_private_address(host) is True


@pytest.mark.parametrize("host", [
    "8.8.8.8",
    "1.1.1.1",
    "2001:4860:4860::8888",
])
def test_public_addresses_rejected(host):
    assert _is_private_address(host) is False


def test_documentation_ranges_count_as_private():
    """Python classifies TEST-NET (192.0.2/24, 198.51.100/24, 203.0.113/24) as
    private, so those ranges are *allowed* and are useless for testing the
    block. Pinned here so nobody reaches for them when writing a repro."""
    assert _is_private_address("203.0.113.9") is True
    assert _is_private_address("198.51.100.4") is True


@pytest.mark.parametrize("host", ["", "testclient", "not-an-ip", "999.999.999.999"])
def test_unparseable_addresses_fail_closed(host):
    assert _is_private_address(host) is False


class _FakeClient:
    def __init__(self, host):
        self.host = host


class _FakeRequest:
    def __init__(self, host, headers=None):
        self.client = _FakeClient(host) if host is not None else None
        self.headers = headers or {}


def _middleware():
    return ExternalRequestMiddleware(app=None)


def test_forwarded_header_ignored_from_untrusted_peer(monkeypatch):
    """A spoofed X-Forwarded-For must not let a public client look private."""
    monkeypatch.setattr(settings, "trusted_proxies", set())
    mw = _middleware()
    request = _FakeRequest("8.8.4.4", {"x-forwarded-for": "127.0.0.1"})
    assert mw._client_host(request) == "8.8.4.4"


def test_forwarded_header_honored_from_trusted_peer(monkeypatch):
    monkeypatch.setattr(settings, "trusted_proxies", {"127.0.0.1"})
    mw = _middleware()
    request = _FakeRequest("127.0.0.1", {"x-forwarded-for": "8.8.4.4, 10.0.0.1"})
    # First entry is the original client.
    assert mw._client_host(request) == "8.8.4.4"


def test_trusted_peer_without_forwarded_header(monkeypatch):
    monkeypatch.setattr(settings, "trusted_proxies", {"127.0.0.1"})
    mw = _middleware()
    assert mw._client_host(_FakeRequest("127.0.0.1")) == "127.0.0.1"


def test_missing_client_yields_empty_host():
    mw = _middleware()
    assert mw._client_host(_FakeRequest(None)) == ""


def test_blocked_logging_is_rate_limited(monkeypatch, tmp_path):
    """A scanner hitting the same address repeatedly writes one entry, not many."""
    from cataloguecanvas import audit

    log_path = tmp_path / "audit.log"
    monkeypatch.setattr(settings, "audit_log_path", log_path)
    monkeypatch.setattr(settings, "audit_log_enabled", True)
    monkeypatch.setattr(settings, "audit_log_max_bytes", 0)

    mw = _middleware()
    for _ in range(50):
        mw._log_blocked("8.8.4.4", "/api/me")

    entries = [e for e in audit.read_events() if e["action"] == "request.blocked_external"]
    assert len(entries) == 1
    assert entries[0]["target"] == "8.8.4.4"


def test_blocked_logging_tracks_distinct_hosts(monkeypatch, tmp_path):
    from cataloguecanvas import audit

    monkeypatch.setattr(settings, "audit_log_path", tmp_path / "audit.log")
    monkeypatch.setattr(settings, "audit_log_enabled", True)
    monkeypatch.setattr(settings, "audit_log_max_bytes", 0)

    mw = _middleware()
    mw._log_blocked("8.8.4.4", "/api/me")
    mw._log_blocked("1.1.1.1", "/api/me")

    entries = [e for e in audit.read_events() if e["action"] == "request.blocked_external"]
    assert {e["target"] for e in entries} == {"8.8.4.4", "1.1.1.1"}


def test_rate_limit_dict_is_bounded(monkeypatch, tmp_path):
    """The per-host timestamp map must not grow without limit."""
    monkeypatch.setattr(settings, "audit_log_path", tmp_path / "audit.log")
    monkeypatch.setattr(settings, "audit_log_enabled", False)  # writes off; only the map matters

    mw = _middleware()
    for i in range(2000):
        mw._log_blocked(f"203.0.113.{i}", "/api/me")

    assert len(mw._last_logged) <= 1200, "expected the rate-limit map to be pruned"


def test_blocked_request_returns_403(monkeypatch):
    """End-to-end through the real app with external requests disabled."""
    from fastapi.testclient import TestClient
    from cataloguecanvas.main import app

    monkeypatch.setattr(settings, "allow_external_requests", False)
    client = TestClient(app)
    resp = client.get("/api/me")
    assert resp.status_code == 403
    assert "external requests are disabled" in resp.json()["detail"]


def test_allowed_when_flag_is_on(monkeypatch):
    from fastapi.testclient import TestClient
    from cataloguecanvas.main import app

    monkeypatch.setattr(settings, "allow_external_requests", True)
    client = TestClient(app)
    assert client.get("/api/me").status_code == 200


def test_public_portfolio_route_is_also_blocked(monkeypatch):
    """Blocking covers public routes too -- that is the point of the default."""
    from fastapi.testclient import TestClient
    from cataloguecanvas.main import app

    monkeypatch.setattr(settings, "allow_external_requests", False)
    client = TestClient(app)
    assert client.get("/api/p/anything").status_code == 403
