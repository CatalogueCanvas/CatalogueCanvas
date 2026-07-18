from __future__ import annotations
import os
import sqlite3
import tempfile
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import httpx
from starlette.background import BackgroundTask
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from ..auth import require_admin
from ..db import get_all_libraries, get_db_stats, get_settings, set_settings
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


def _settings_response(conn: sqlite3.Connection) -> dict:
    stored = get_settings(conn)
    return {
        **{k: stored.get(k, v) for k, v in LLM_DEFAULTS.items()},
        **{k: stored.get(k, v) for k, v in APPEARANCE_DEFAULTS.items()},
        **{k: stored.get(k, v) for k, v in UPDATE_DEFAULTS.items()},
        "llm_prompt_template": stored.get("llm_prompt_template") or default_prompt_template(),
        "llm_prompt_template_default": default_prompt_template(),
        "stats": get_db_stats(conn),
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


@router.put("")
def update_settings_endpoint(
    body: SettingsUpdate,
    conn: sqlite3.Connection = Depends(get_db),
    _: None = Depends(require_admin),
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


@router.post("/diagnostics")
def diagnostics(_: None = Depends(require_admin)):
    from ..diagnostics import build_report

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    report = build_report()
    return Response(
        content=report,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="cataloguecanvas-diagnostics-{timestamp}.md"'},
    )


@router.post("/export/db")
def export_db(_: None = Depends(require_admin)):
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
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
def export_all(conn: sqlite3.Connection = Depends(get_db), _: None = Depends(require_admin)):
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp_path = Path(tmp.name)
    tmp.close()

    db_conn = sqlite3.connect(str(settings.db_path))
    try:
        db_conn.execute("VACUUM INTO ?", (str(tmp_path),))
    finally:
        db_conn.close()

    zip_tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    zip_path = Path(zip_tmp.name)
    zip_tmp.close()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(tmp_path, "catalogue.db")
        for lib in get_all_libraries(conn):
            lib_root = Path(lib["path"])
            if not lib_root.exists():
                continue
            lib_root = lib_root.resolve()
            for path in lib_root.rglob("*"):
                # Skip symlinks (and anything they point outside the root) so the
                # backup can't be tricked into exfiltrating arbitrary files.
                if path.is_symlink() or not path.is_file():
                    continue
                resolved = path.resolve()
                if resolved != lib_root and not str(resolved).startswith(str(lib_root) + os.sep):
                    continue
                zf.write(path, Path("storage") / lib["id"] / path.relative_to(lib_root))
    tmp_path.unlink(missing_ok=True)

    filename = f"cataloguecanvas-backup-{timestamp}.zip"
    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename=filename,
        background=BackgroundTask(zip_path.unlink, missing_ok=True),
    )
