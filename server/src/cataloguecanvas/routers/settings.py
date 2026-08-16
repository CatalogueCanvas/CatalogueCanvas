from __future__ import annotations
import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import httpx
from starlette.background import BackgroundTask
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from .. import audit
from ..auth import require_admin
from ..backup import create_backup
from ..db import get_db_stats, get_settings, set_settings
from ..diagnostics import _app_version
from ..llm import LLMError, _normalize_api_url, _validate_api_url, default_prompt_template
from ..settings import settings
from .auth import get_db

router = APIRouter(prefix="/api/settings", tags=["settings"])

# GitHub release source and how often we're allowed to poll it when the opt-in
# update check is enabled. The result is cached in app_settings so a page load
# never triggers more than one outbound call per week (unless forced).
#
# The repo publishes versions as git tags (vX.Y.Z) via CI; formal GitHub Releases
# may not exist, so /releases/latest can 404. We therefore read /tags and pick the
# highest semver, which works whether or not a Release has been published.
GITHUB_TAGS_URL = "https://api.github.com/repos/CatalogueCanvas/CatalogueCanvas/tags"
UPDATE_CHECK_INTERVAL = timedelta(days=7)

LLM_DEFAULTS = {
    "llm_api_url": "",
    "llm_model": "",
    "llm_item_type": "image",
    "llm_summary_focus": "the item's notable characteristics",
    "llm_bullet_count": "3",
    "llm_bullet_max_words": "50",
    "llm_auto_generate": "false",
    "llm_timeout": "90",
}

APPEARANCE_DEFAULTS = {
    "theme": "light",
    "accent": "default",
    "nav": "top",
    "density": "balanced",
    "favorites_enabled": "true",
    "multi_user_enabled": "false",
}

# Admin-only update-check state. Kept out of APPEARANCE_DEFAULTS so it is never
# served on the public /appearance endpoint.
UPDATE_DEFAULTS = {
    "update_check_enabled": "false",
    "update_last_checked": "",
    "update_latest_version": "",
}

# Admin-only telemetry state. Kept out of APPEARANCE_DEFAULTS so it is never
# served on the public /appearance endpoint.
TELEMETRY_DEFAULTS = {
    "usage_stats_enabled": "false",
    "usage_last_sent": "",
}


def _settings_response(conn: sqlite3.Connection) -> dict:
    stored = get_settings(conn)
    return {
        **{k: stored.get(k, v) for k, v in LLM_DEFAULTS.items()},
        **{k: stored.get(k, v) for k, v in APPEARANCE_DEFAULTS.items()},
        **{k: stored.get(k, v) for k, v in UPDATE_DEFAULTS.items()},
        **{k: stored.get(k, v) for k, v in TELEMETRY_DEFAULTS.items()},
        "llm_prompt_template": stored.get("llm_prompt_template") or default_prompt_template(),
        "llm_prompt_template_default": default_prompt_template(),
        "stats": get_db_stats(conn),
        # Env-controlled, read-only from the UI's point of view -- surfaced so an
        # admin can see the effective access policy without shell access.
        "access": {
            "allow_external_requests": settings.allow_external_requests,
            "trusted_proxies": sorted(settings.trusted_proxies),
        },
    }


@router.get("")
def get_settings_endpoint(conn: sqlite3.Connection = Depends(get_db), _: None = Depends(require_admin)):
    return _settings_response(conn)


@router.get("/appearance")
def get_appearance_endpoint(conn: sqlite3.Connection = Depends(get_db)):
    stored = get_settings(conn)
    return {k: stored.get(k, v) for k, v in APPEARANCE_DEFAULTS.items()}


class SettingsUpdate(BaseModel):
    llm_api_url: Optional[str] = None
    llm_model: Optional[str] = None
    llm_item_type: Optional[str] = None
    llm_summary_focus: Optional[str] = None
    llm_bullet_count: Optional[str] = None
    llm_bullet_max_words: Optional[str] = None
    llm_auto_generate: Optional[str] = None
    llm_prompt_template: Optional[str] = None
    llm_timeout: Optional[str] = None
    theme: Optional[str] = None
    accent: Optional[str] = None
    nav: Optional[str] = None
    density: Optional[str] = None
    favorites_enabled: Optional[str] = None
    multi_user_enabled: Optional[str] = None
    update_check_enabled: Optional[str] = None
    usage_stats_enabled: Optional[str] = None


@router.put("")
def update_settings_endpoint(
    body: SettingsUpdate,
    conn: sqlite3.Connection = Depends(get_db),
    actor: str = Depends(require_admin),
):
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    # Re-validate the LLM endpoint here so a non-allowlisted or malformed host is
    # rejected at save time, not just when a describe call happens to run.
    api_url = fields.get("llm_api_url")
    if api_url:
        try:
            _validate_api_url(_normalize_api_url(api_url))
        except LLMError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    set_settings(conn, fields)
    # Keys only: values carry the LLM api_url and the whole prompt template.
    audit.log_event("settings.update", actor=actor, role="admin", fields=sorted(fields.keys()))
    return _settings_response(conn)


# Update-check endpoint lives outside the /api/settings prefix.
version_router = APIRouter(tags=["version"])


def _version_tuple(v: str) -> tuple[int, ...]:
    """Parse a version like '0.1.2' (or 'v0.1.2') into a comparable tuple.

    Non-numeric or missing parts degrade to 0 so a malformed tag can never make
    an update look available; comparison stays best-effort.
    """
    parts = v.strip().lstrip("v").split(".")
    out = []
    for p in parts:
        num = "".join(ch for ch in p if ch.isdigit())
        out.append(int(num) if num else 0)
    return tuple(out)


def _fetch_latest_release() -> Optional[str]:
    """Return the highest semver tag from GitHub, or None if there are none.

    Reads the tags list (not /releases/latest, which 404s when no formal Release
    is published) and picks the tag with the greatest version tuple.
    """
    resp = httpx.get(
        GITHUB_TAGS_URL,
        timeout=10.0,
        headers={"Accept": "application/vnd.github+json"},
    )
    resp.raise_for_status()
    tags = [
        t["name"].lstrip("v")
        for t in resp.json()
        if isinstance(t, dict) and isinstance(t.get("name"), str) and t["name"]
    ]
    if not tags:
        return None
    return max(tags, key=_version_tuple)


@version_router.get("/api/version")
def get_version(
    force: bool = False,
    conn: sqlite3.Connection = Depends(get_db),
    _: None = Depends(require_admin),
):
    # Piggyback the throttled weekly usage ping on this endpoint: it runs on
    # Settings page load and is admin-gated, giving a once-a-week outbound
    # wakeup without any scheduler. No-op unless usage stats are enabled.
    from .. import telemetry

    telemetry.maybe_send_weekly(conn)

    current = _app_version()
    stored = get_settings(conn)
    enabled = stored.get("update_check_enabled", "false") == "true"
    cached_latest = stored.get("update_latest_version") or None
    last_checked = stored.get("update_last_checked") or None

    def _result(latest: Optional[str], checked: bool) -> dict:
        available = bool(latest) and _version_tuple(latest) > _version_tuple(current)
        return {
            "current": current,
            "latest": latest,
            "update_available": available,
            "checked": checked,
            "last_checked": last_checked,
        }

    if not enabled:
        # No outbound call; surface any previously cached result only.
        return _result(cached_latest, False)

    # Throttle: only poll GitHub when forced or the cache is older than a week.
    due = force or not last_checked
    if last_checked and not force:
        try:
            due = datetime.now(timezone.utc) - datetime.fromisoformat(last_checked) >= UPDATE_CHECK_INTERVAL
        except ValueError:
            due = True
    if not due:
        return _result(cached_latest, False)

    try:
        latest = _fetch_latest_release()
    except (httpx.HTTPError, ValueError):
        # Network/rate-limit/parse failure: keep the old cache and timestamp so
        # the next enabled load retries rather than sticking on a stale success.
        return _result(cached_latest, True)

    last_checked = datetime.now(timezone.utc).isoformat()
    set_settings(conn, {"update_latest_version": latest or "", "update_last_checked": last_checked})
    return _result(latest, True)


# --- activity log ---

# Typed confirmation phrase, mirroring the CSV backup delete. Exported to the
# client so both sides agree on the exact string.
DELETE_ACTIVITY_CONFIRM = "delete activity log"


@router.get("/activity")
def get_activity(limit: int = 200, _: str = Depends(require_admin)):
    """Recent activity entries, newest first, for the Settings panel."""
    limit = max(1, min(2000, limit))
    return {
        "entries": audit.read_events(limit=limit),
        "enabled": settings.audit_log_enabled,
        "path": str(settings.audit_log_path),
    }


@router.post("/activity/export")
def export_activity(actor: str = Depends(require_admin)):
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    audit.log_event("activity.export", actor=actor, role="admin")
    return Response(
        content=audit.export_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="cataloguecanvas-activity-{timestamp}.csv"'},
    )


class DeleteActivity(BaseModel):
    confirm: str


@router.delete("/activity")
def delete_activity(body: DeleteActivity, actor: str = Depends(require_admin)):
    """Clear the activity log. Requires a typed confirmation phrase."""
    if body.confirm.strip() != DELETE_ACTIVITY_CONFIRM:
        raise HTTPException(status_code=400, detail=f'type "{DELETE_ACTIVITY_CONFIRM}" to confirm')
    audit.clear()
    # Written after the truncation, so a cleared log still shows who cleared it
    # rather than looking like it was never used.
    audit.log_event("activity.clear", actor=actor, role="admin")
    return {"ok": True}


@router.post("/diagnostics")
def diagnostics(_: str = Depends(require_admin)):
    from ..diagnostics import build_report

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    report = build_report()
    return Response(
        content=report,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="cataloguecanvas-diagnostics-{timestamp}.md"'},
    )


@router.post("/export/db")
def export_db(actor: str = Depends(require_admin)):
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    audit.log_event("export.database", actor=actor, role="admin")
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp_path = Path(tmp.name)
    tmp.close()

    conn = sqlite3.connect(str(settings.db_path))
    try:
        conn.execute("VACUUM INTO ?", (str(tmp_path),))
    finally:
        conn.close()

    return FileResponse(
        tmp_path,
        media_type="application/octet-stream",
        filename=f"catalogue-{timestamp}.db",
        background=BackgroundTask(tmp_path.unlink, missing_ok=True),
    )


@router.post("/export/all")
def export_all(conn: sqlite3.Connection = Depends(get_db), actor: str = Depends(require_admin)):
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    audit.log_event("export.full_backup", actor=actor, role="admin")

    zip_tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    zip_path = Path(zip_tmp.name)
    zip_tmp.close()
    # Same archive layout the `cc backup` CLI writes and `cc restore` reads.
    create_backup(conn, zip_path)

    filename = f"cataloguecanvas-backup-{timestamp}.zip"
    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename=filename,
        background=BackgroundTask(zip_path.unlink, missing_ok=True),
    )
