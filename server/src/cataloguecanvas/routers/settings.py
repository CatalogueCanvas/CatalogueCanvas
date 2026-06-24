from __future__ import annotations
import os
import sqlite3
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from starlette.background import BackgroundTask
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from ..auth import require_admin
from ..db import get_all_libraries, get_db_stats, get_settings, set_settings
from ..llm import LLMError, _normalize_api_url, _validate_api_url, default_prompt_template
from ..settings import settings
from .auth import get_db

router = APIRouter(prefix="/api/settings", tags=["settings"])

LLM_DEFAULTS = {
    "llm_api_url": "",
    "llm_model": "",
    "llm_item_type": "image",
    "llm_summary_focus": "the item's notable characteristics",
    "llm_bullet_count": "3",
    "llm_bullet_max_words": "50",
    "llm_auto_generate": "false",
}

APPEARANCE_DEFAULTS = {
    "theme": "light",
    "accent": "default",
    "nav": "top",
    "density": "balanced",
    "favorites_enabled": "true",
    "multi_user_enabled": "false",
}


def _settings_response(conn: sqlite3.Connection) -> dict:
    stored = get_settings(conn)
    return {
        **{k: stored.get(k, v) for k, v in LLM_DEFAULTS.items()},
        **{k: stored.get(k, v) for k, v in APPEARANCE_DEFAULTS.items()},
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
    theme: Optional[str] = None
    accent: Optional[str] = None
    nav: Optional[str] = None
    density: Optional[str] = None
    favorites_enabled: Optional[str] = None
    multi_user_enabled: Optional[str] = None


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
