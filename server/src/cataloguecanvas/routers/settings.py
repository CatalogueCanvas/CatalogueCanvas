from __future__ import annotations
import sqlite3
import tempfile
import zipfile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Optional

from starlette.background import BackgroundTask
from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import BaseModel

from ..auth import require_admin
from ..db import get_all_libraries, get_db_stats, get_settings, set_settings
from ..llm import default_prompt_template
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
    set_settings(conn, fields)
    return _settings_response(conn)


@router.get("/diagnostics")
def diagnostics(_: None = Depends(require_admin)):
    from ..diagnostics import build_report

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    report = build_report()
    return Response(
        content=report,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="cataloguecanvas-diagnostics-{timestamp}.md"'},
    )


@router.get("/export/db")
def export_db(_: None = Depends(require_admin)):
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp_path = Path(tmp.name)
    tmp.close()

    conn = sqlite3.connect(str(settings.db_path))
    try:
        conn.execute(f"VACUUM INTO '{tmp_path}'")
    finally:
        conn.close()

    return FileResponse(
        tmp_path,
        media_type="application/octet-stream",
        filename=f"catalogue-{timestamp}.db",
        background=BackgroundTask(tmp_path.unlink, missing_ok=True),
    )


@router.get("/export/all")
def export_all(conn: sqlite3.Connection = Depends(get_db), _: None = Depends(require_admin)):
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp_path = Path(tmp.name)
    tmp.close()

    db_conn = sqlite3.connect(str(settings.db_path))
    try:
        db_conn.execute(f"VACUUM INTO '{tmp_path}'")
    finally:
        db_conn.close()

    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(tmp_path, "catalogue.db")
        for lib in get_all_libraries(conn):
            lib_root = Path(lib["path"])
            if lib_root.exists():
                for path in lib_root.rglob("*"):
                    if path.is_file():
                        zf.write(path, Path("storage") / lib["id"] / path.relative_to(lib_root))
    tmp_path.unlink(missing_ok=True)
    buffer.seek(0)

    filename = f"cataloguecanvas-backup-{timestamp}.zip"
    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
