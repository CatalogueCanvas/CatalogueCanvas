"""Tests for anonymous opt-in telemetry.

Network is mocked (telemetry.httpx.post) so nothing leaves the machine. We
exercise: the install opt-in gate and one-time flag, the weekly enable gate and
weekly throttle, network-failure isolation, and the payload shape (no PII keys).
"""
from __future__ import annotations

import httpx
import pytest

from cataloguecanvas import db, telemetry
from cataloguecanvas.settings import settings


class _Capture:
    """Record calls to telemetry.httpx.post and return a canned response."""

    def __init__(self, status: int = 200, raises: Exception | None = None):
        self.status = status
        self.raises = raises
        self.calls: list[dict] = []

    def __call__(self, url, **kwargs):
        self.calls.append({"url": url, "json": kwargs.get("json")})
        if self.raises is not None:
            raise self.raises
        return httpx.Response(self.status, json={"status": "Ok"}, request=httpx.Request("POST", url))


@pytest.fixture()
def install_db(monkeypatch, tmp_path):
    """A schema-applied db on settings.db_path so send_install_ping (which opens
    its own connection) sees a real table; install tracking forced on."""
    conn = db.get_connection(settings.db_path)
    db.ensure_schema(conn)
    # Start clean so a prior test's flag doesn't leak in.
    conn.execute("DELETE FROM app_settings WHERE key = 'install_ping_sent'")
    conn.commit()
    conn.close()
    monkeypatch.setattr(settings, "install_tracking", True)
    monkeypatch.setattr(settings, "posthog_key", "phc_test")
    yield


def test_capture_sends_expected_body(monkeypatch):
    cap = _Capture()
    monkeypatch.setattr(telemetry.httpx, "post", cap)
    monkeypatch.setattr(settings, "posthog_key", "phc_test")

    assert telemetry.capture("some_event", {"a": 1}) is True
    assert len(cap.calls) == 1
    body = cap.calls[0]["json"]
    assert body["api_key"] == "phc_test"
    assert body["event"] == "some_event"
    assert body["distinct_id"]  # anonymous id present
    assert body["properties"] == {"a": 1}


def test_capture_no_key_is_noop(monkeypatch):
    cap = _Capture()
    monkeypatch.setattr(telemetry.httpx, "post", cap)
    monkeypatch.setattr(settings, "posthog_key", "")

    assert telemetry.capture("e", {}) is False
    assert cap.calls == []


def test_capture_swallows_network_error(monkeypatch):
    cap = _Capture(raises=httpx.ConnectError("boom", request=httpx.Request("POST", "http://x")))
    monkeypatch.setattr(telemetry.httpx, "post", cap)
    monkeypatch.setattr(settings, "posthog_key", "phc_test")

    # Must not raise; returns False on failure.
    assert telemetry.capture("e", {}) is False


def test_install_ping_opt_out(monkeypatch):
    cap = _Capture()
    monkeypatch.setattr(telemetry.httpx, "post", cap)
    monkeypatch.setattr(settings, "install_tracking", False)

    telemetry.send_install_ping()
    assert cap.calls == []


def test_install_ping_fires_once(monkeypatch, install_db):
    cap = _Capture()
    monkeypatch.setattr(telemetry.httpx, "post", cap)

    telemetry.send_install_ping()
    telemetry.send_install_ping()  # flag now set: must be a no-op

    assert len(cap.calls) == 1
    assert cap.calls[0]["json"]["event"] == "catalogue_install"


def test_weekly_disabled_is_noop(conn, monkeypatch):
    cap = _Capture()
    monkeypatch.setattr(telemetry.httpx, "post", cap)
    monkeypatch.setattr(settings, "posthog_key", "phc_test")
    # usage_stats_enabled defaults to unset/false
    telemetry.maybe_send_weekly(conn)
    assert cap.calls == []


def test_weekly_enabled_fires_then_throttles(conn, monkeypatch):
    cap = _Capture()
    monkeypatch.setattr(telemetry.httpx, "post", cap)
    monkeypatch.setattr(settings, "posthog_key", "phc_test")
    db.set_settings(conn, {"usage_stats_enabled": "true"})

    telemetry.maybe_send_weekly(conn)
    telemetry.maybe_send_weekly(conn)  # within a week: throttled

    assert len(cap.calls) == 1
    assert cap.calls[0]["json"]["event"] == "catalogue_weekly"
    # timestamp was persisted
    assert db.get_settings(conn).get("usage_last_sent")


def test_weekly_payload_has_no_pii(conn, monkeypatch):
    cap = _Capture()
    monkeypatch.setattr(telemetry.httpx, "post", cap)
    monkeypatch.setattr(settings, "posthog_key", "phc_test")
    db.set_settings(conn, {"usage_stats_enabled": "true"})

    telemetry.maybe_send_weekly(conn)
    props = cap.calls[0]["json"]["properties"]

    assert set(props.keys()) == {
        "version", "git_sha", "install_type", "os",
        "item_count", "db_size_bytes", "ram_total_bytes",
    }
