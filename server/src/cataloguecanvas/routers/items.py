from __future__ import annotations
import json
import mimetypes
import sqlite3
import zipfile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any, Optional

import lz4.frame
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

from ..auth import require_admin
from ..db import delete_item, get_all_items, get_item, update_item_meta
from ..ingest import ingest_zip_bytes
from ..llm import LLMError, describe
from ..settings import settings
from .auth import get_db

router = APIRouter(prefix="/api/items", tags=["items"])


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp", ".tiff", ".tif"}
TEXT_EXTS = {
    ".txt", ".md", ".json", ".toml", ".yaml", ".yml", ".csv",
    ".py", ".r", ".js", ".ts", ".tsx", ".jsx", ".p5", ".html", ".css", ".sh",
}


def _file_type(path: str) -> str:
    name = path[:-4] if path.lower().endswith(".lz4") else path
    ext = Path(name).suffix.lower()
    if ext in IMAGE_EXTS:
        return "image"
    if ext in TEXT_EXTS:
        return "text"
    return "other"


def _json_field(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value if value is not None else []


def _enrich(item: dict[str, Any]) -> dict[str, Any]:
    item = dict(item)
    item["tags"] = _json_field(item.get("tags"))
    item["raw_meta"] = _json_field(item.get("raw_meta")) or {}
    other_files = _json_field(item.get("other_files"))
    item["other_files"] = other_files

    if item.get("preview_path"):
        item["preview_url"] = f"/storage/{item['preview_path']}"
    else:
        item["preview_url"] = None

    item["download_urls"] = [
        {
            "name": Path(f[:-4] if f.lower().endswith(".lz4") else f).name,
            "url": f"/api/items/{item['id']}/raw/{Path(f).name}" if f.lower().endswith(".lz4") else f"/storage/{f}",
            "type": _file_type(f),
        }
        for f in other_files
    ]

    if not item.get("title"):
        item["title"] = item["id"].replace("-", " ").title()

    return item


@router.get("")
def list_items(conn: sqlite3.Connection = Depends(get_db), _: None = Depends(require_admin)):
    return [_enrich(i) for i in get_all_items(conn)]


class BulkIds(BaseModel):
    item_ids: list[str]


@router.post("/bulk/clear-notes")
def bulk_clear_notes(body: BulkIds, conn: sqlite3.Connection = Depends(get_db), _: None = Depends(require_admin)):
    updated, missing = [], []
    for item_id in body.item_ids:
        if get_item(conn, item_id):
            update_item_meta(conn, item_id, {"note": ""})
            updated.append(item_id)
        else:
            missing.append(item_id)
    return {"updated": updated, "missing": missing}


class BulkTags(BaseModel):
    item_ids: list[str]
    tags: list[str]


@router.post("/bulk/tags")
def bulk_add_tags(body: BulkTags, conn: sqlite3.Connection = Depends(get_db), _: None = Depends(require_admin)):
    updated, missing = [], []
    for item_id in body.item_ids:
        item = get_item(conn, item_id)
        if not item:
            missing.append(item_id)
            continue
        existing_tags = _json_field(item.get("tags")) or []
        merged = list(existing_tags)
        for tag in body.tags:
            if tag not in merged:
                merged.append(tag)
        update_item_meta(conn, item_id, {"tags": merged})
        updated.append(item_id)
    return {"updated": updated, "missing": missing}


@router.post("/archive")
def bulk_archive_items(body: BulkIds, conn: sqlite3.Connection = Depends(get_db), _: None = Depends(require_admin)):
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for item_id in body.item_ids:
            item = get_item(conn, item_id)
            if item:
                _write_item_to_zip(zf, item, prefix=f"{item_id}/")
    buffer.seek(0)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="items_bulk_{timestamp}.zip"'},
    )


@router.get("/{item_id}")
def get_item_endpoint(item_id: str, conn: sqlite3.Connection = Depends(get_db), _: None = Depends(require_admin)):
    item = get_item(conn, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="item not found")
    return _enrich(item)


@router.get("/{item_id}/raw/{filename}")
def raw_file(item_id: str, filename: str, conn: sqlite3.Connection = Depends(get_db), _: None = Depends(require_admin)):
    item = get_item(conn, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="item not found")
    other_files = _json_field(item.get("other_files"))
    match = next((f for f in other_files if f.lower().endswith(".lz4") and Path(f).name == f"{filename}.lz4"), None)
    if not match:
        raise HTTPException(status_code=404, detail="file not found")
    file_path = settings.storage_dir / match
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="file not found")
    data = lz4.frame.decompress(file_path.read_bytes())
    media_type, _ = mimetypes.guess_type(filename)
    return Response(content=data, media_type=media_type or "application/octet-stream")


def _write_item_to_zip(zf: zipfile.ZipFile, item: dict[str, Any], prefix: str = "") -> None:
    other_files = _json_field(item.get("other_files"))
    if item.get("preview_path"):
        preview_path = settings.storage_dir / item["preview_path"]
        if preview_path.exists():
            zf.write(preview_path, f"{prefix}{Path(item['preview_path']).name}")
    for f in other_files:
        file_path = settings.storage_dir / f
        if not file_path.exists():
            continue
        if f.lower().endswith(".lz4"):
            zf.writestr(f"{prefix}{Path(f[:-4]).name}", lz4.frame.decompress(file_path.read_bytes()))
        else:
            zf.write(file_path, f"{prefix}{Path(f).name}")


@router.get("/{item_id}/archive")
def archive_item(item_id: str, conn: sqlite3.Connection = Depends(get_db), _: None = Depends(require_admin)):
    item = get_item(conn, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="item not found")

    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        _write_item_to_zip(zf, item)
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{item_id}.zip"'},
    )


@router.post("/upload")
async def upload_item(
    file: UploadFile = File(...),
    conn: sqlite3.Connection = Depends(get_db),
    _: None = Depends(require_admin),
):
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="only .zip files are supported")

    data = await file.read()
    import_dt = datetime.now(timezone.utc).isoformat(timespec="seconds")
    result = ingest_zip_bytes(
        data,
        file.filename,
        conn,
        settings.storage_dir,
        import_dt=import_dt,
    )
    return {
        "item": _enrich(result.item) if result.item else None,
        "created": result.created,
        "note": result.note,
    }


class ItemUpdate(BaseModel):
    title: Optional[str] = None
    note: Optional[str] = None
    tags: Optional[list[str]] = None
    collection_id: Optional[str] = None
    raw_meta: Optional[dict] = None


@router.patch("/{item_id}")
def update_item(
    item_id: str,
    body: ItemUpdate,
    conn: sqlite3.Connection = Depends(get_db),
    _: None = Depends(require_admin),
):
    if not get_item(conn, item_id):
        raise HTTPException(status_code=404, detail="item not found")
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    updated = update_item_meta(conn, item_id, fields)
    return _enrich(updated)


@router.delete("/{item_id}")
def delete_item_endpoint(item_id: str, conn: sqlite3.Connection = Depends(get_db), _: None = Depends(require_admin)):
    if not get_item(conn, item_id):
        raise HTTPException(status_code=404, detail="item not found")
    delete_item(conn, item_id)
    return {"ok": True}


class DescribeRequest(BaseModel):
    api_url: str
    model: str
    item_type: str = "image"
    summary_focus: str = "the item's notable characteristics"
    bullet_count: int = 3
    bullet_max_words: int = 50
    prompt_template: Optional[str] = None
    api_key: Optional[str] = None


@router.post("/{item_id}/describe")
def describe_item(
    item_id: str,
    body: DescribeRequest,
    conn: sqlite3.Connection = Depends(get_db),
    _: None = Depends(require_admin),
):
    item = get_item(conn, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="item not found")
    if not item.get("preview_path"):
        raise HTTPException(status_code=400, detail="item has no preview image")

    preview_path = settings.storage_dir / item["preview_path"]
    if not preview_path.exists():
        raise HTTPException(status_code=404, detail="preview image not found on disk")

    image_bytes = preview_path.read_bytes()
    try:
        result = describe(
            image_bytes,
            api_url=body.api_url,
            model=body.model,
            item_type=body.item_type,
            summary_focus=body.summary_focus,
            bullet_count=body.bullet_count,
            bullet_max_words=body.bullet_max_words,
            prompt_template=body.prompt_template,
            api_key=body.api_key,
        )
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return result
