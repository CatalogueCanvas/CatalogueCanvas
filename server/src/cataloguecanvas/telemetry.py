"""Anonymous, opt-in telemetry.

Two events, both off unless explicitly enabled, both keyed by a random per-instance
UUID (persisted under the data dir) so an install ping and later weekly pings can
be correlated without ever sending anything identifying:

- ``catalogue_install`` — fired once on first boot, only when ``CC_INSTALL_TRACKING=1``.
- ``catalogue_weekly``  — recurring, only when the ``usage_stats_enabled`` setting is
  on; throttled to once per week via a stored timestamp (mirrors the update-check
  throttle in ``routers/settings.py`` since there is no scheduler in the app).

Payloads contain only coarse, non-identifying fields (version, install type, OS,
db size, item count, total RAM). No hostname, IP, paths, filenames, user data, or
LLM config is ever sent. All network failures are swallowed: telemetry must never
break a boot or a request.
"""
from __future__ import annotations
import platform
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import httpx

from .db import get_db_stats, get_settings, set_settings
from .diagnostics import _app_version, _git_sha
from .settings import settings

WEEKLY_INTERVAL = timedelta(days=7)


def _instance_id() -> str:
    """Return the persisted anonymous instance UUID, creating it once if absent.

    Same persist-under-data-dir pattern as the session secret key.
    """
    path = settings.data_dir / "instance_id"
    try:
        existing = path.read_text().strip()
        if existing:
            return existing
    except OSError:
        pass
    new_id = uuid.uuid4().hex
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(new_id)
        path.chmod(0o600)
    except OSError:
        pass
    return new_id


def _install_type() -> str:
    """Best-effort 'docker' vs 'bare-metal' detection."""
    if Path("/.dockerenv").exists() or str(settings.data_dir) == "/data":
        return "docker"
    return "bare-metal"


def _ram_total_bytes() -> Optional[int]:
    try:
        import psutil

        return int(psutil.virtual_memory().total)
    except Exception:
        return None


def _base_props() -> dict:
    return {
        "version": _app_version(),
        "git_sha": _git_sha(),
        "install_type": _install_type(),
        "os": platform.platform(),
    }


def _collect_stats(conn: sqlite3.Connection) -> dict:
    props = _base_props()
    try:
        props["item_count"] = get_db_stats(conn).get("total_items")
    except sqlite3.Error:
        props["item_count"] = None
    try:
        props["db_size_bytes"] = settings.db_path.stat().st_size
    except OSError:
        props["db_size_bytes"] = None
    props["ram_total_bytes"] = _ram_total_bytes()
    return props


def capture(event: str, properties: dict) -> bool:
    """POST one event to PostHog. Returns True on a 2xx, False on any failure.

    Never raises — telemetry must not affect the caller.
    """
    if not settings.posthog_key:
        return False
    try:
        resp = httpx.post(
            f"{settings.posthog_host.rstrip('/')}/capture/",
            json={
                "api_key": settings.posthog_key,
                "event": event,
                "distinct_id": _instance_id(),
                "properties": properties,
            },
            timeout=10.0,
        )
        resp.raise_for_status()
        return True
    except (httpx.HTTPError, ValueError, OSError):
        return False


def send_install_ping() -> None:
    """Fire the one-time install event, guarded by opt-in env var and a stored flag.

    Safe to call on every boot: no-op unless CC_INSTALL_TRACKING=1 and the flag has
    not already been set.
    """
    if not settings.install_tracking:
        return
    conn = sqlite3.connect(str(settings.db_path))
    conn.row_factory = sqlite3.Row
    try:
        if get_settings(conn).get("install_ping_sent") == "true":
            return
        if capture("catalogue_install", _base_props()):
            set_settings(conn, {"install_ping_sent": "true"})
    finally:
        conn.close()


def maybe_send_weekly(conn: sqlite3.Connection) -> None:
    """Fire the weekly stats event if enabled and at least a week has elapsed.

    No-op unless usage_stats_enabled is on. Throttled via the usage_last_sent
    timestamp so a page load never sends more than one event per week.
    """
    stored = get_settings(conn)
    if stored.get("usage_stats_enabled", "false") != "true":
        return

    last_sent = stored.get("usage_last_sent") or None
    if last_sent:
        try:
            if datetime.now(timezone.utc) - datetime.fromisoformat(last_sent) < WEEKLY_INTERVAL:
                return
        except ValueError:
            pass  # malformed timestamp: treat as due

    if capture("catalogue_weekly", _collect_stats(conn)):
        set_settings(conn, {"usage_last_sent": datetime.now(timezone.utc).isoformat()})
