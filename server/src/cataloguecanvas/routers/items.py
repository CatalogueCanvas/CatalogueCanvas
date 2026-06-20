from __future__ import annotations
import csv
import json
import sqlite3
import zipfile
from datetime import datetime, timezone
from io import BytesIO, StringIO
from pathlib import Path
from typing import Any, Optional

import lz4.frame
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

from ..auth import require_admin, require_session
from ..db import (
    add_item_to_collection,
    delete_item,
    get_all_items,
    get_default_library,
    get_item,
    get_library,
    remove_item_from_collection,
    search_items,
    set_item_collections,
    update_item_meta,
)
from ..ingest import ingest_zip_bytes
from ..llm import LLMError, describe
from ..settings import settings
from .auth import get_db

router = APIRouter(prefix="/api/items", tags=["items"])


# CSV round-trip: only title/note/tags are read back on import. The remaining
# columns are exported for reference/context but are ignored when re-uploaded.
CSV_EDITABLE_COLUMNS = ["title", "note", "tags"]
CSV_READONLY_COLUMNS = ["mime_type", "ingested_at", "collection_ids"]
CSV_COLUMNS = ["id", *CSV_EDITABLE_COLUMNS, *CSV_READONLY_COLUMNS]
CSV_TAGS_SEP = "; "
CSV_BACKUP_KEEP = 20


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp", ".tiff", ".tif"}
TEXT_EXTS = {
    ".txt", ".md", ".json", ".toml", ".yaml", ".yml", ".csv",
    ".py", ".r", ".js", ".ts", ".tsx", ".jsx", ".p5", ".html", ".css", ".sh",
}


def _file_type(path: str) -> str:
    # Compressed files are served raw and are download-only — never rendered
    # in-browser, regardless of the inner extension.
    if path.lower().endswith(".lz4"):
        return "other"
    ext = Path(path).suffix.lower()
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

    library_id = item.get("library_id")

    if item.get("preview_path"):
        item["preview_url"] = f"/storage/{library_id}/{item['preview_path']}"
    else:
        item["preview_url"] = None

    item["download_urls"] = [
        {
            # Compressed files download as-is, so show the full stored name.
            "name": Path(f).name,
            "url": f"/api/items/{item['id']}/raw/{Path(f).name}" if f.lower().endswith(".lz4") else f"/storage/{library_id}/{f}",
            "type": _file_type(f),
        }
        for f in other_files
    ]

    if not item.get("title"):
        item["title"] = item["id"].replace("-", " ").title()

    return item


def _tags_to_cell(tags: Any) -> str:
    tags = _json_field(tags)
    if isinstance(tags, list):
        return CSV_TAGS_SEP.join(str(t) for t in tags)
    return str(tags or "")


def _cell_to_tags(cell: str) -> list[str]:
    parts = [t.strip() for t in (cell or "").replace(",", ";").split(";")]
    return [t for t in parts if t]


def _csv_changes(conn: sqlite3.Connection, file_bytes: bytes) -> dict[str, Any]:
    """Parse an uploaded CSV and compute the change set against the DB without
    writing. Rows are matched on `id`; unknown/blank ids are skipped. Only
    title/note/tags are considered."""
    text = file_bytes.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(StringIO(text))
    to_update: list[dict[str, Any]] = []
    skipped: list[str] = []
    unchanged: list[str] = []
    total = 0
    for row in reader:
        total += 1
        item_id = (row.get("id") or "").strip()
        if not item_id:
            skipped.append("")
            continue
        item = get_item(conn, item_id)
        if not item:
            skipped.append(item_id)
            continue

        diff: dict[str, Any] = {"id": item_id}
        # title
        if "title" in row:
            new_title = (row.get("title") or "").strip()
            old_title = item.get("title") or ""
            if new_title != old_title:
                diff["title"] = {"old": old_title, "new": new_title}
        # note
        if "note" in row:
            new_note = row.get("note") or ""
            old_note = item.get("note") or ""
            if new_note != old_note:
                diff["note"] = {"old": old_note, "new": new_note}
        # tags
        if "tags" in row:
            new_tags = _cell_to_tags(row.get("tags") or "")
            old_tags = _json_field(item.get("tags")) or []
            if not isinstance(old_tags, list):
                old_tags = []
            if new_tags != old_tags:
                diff["tags"] = {"old": old_tags, "new": new_tags}

        if len(diff) > 1:
            to_update.append(diff)
        else:
            unchanged.append(item_id)

    return {"to_update": to_update, "skipped": skipped, "unchanged": unchanged, "total_rows": total}


def _write_csv_backup(conn: sqlite3.Connection, item_ids: list[str]) -> str:
    """Snapshot current title/note/tags for the given items to a timestamped,
    lz4-compressed JSON file under CC_DATA_DIR/backups. Returns the filename.
    Keeps only the most recent CSV_BACKUP_KEEP backups."""
    snapshot = []
    for item_id in item_ids:
        item = get_item(conn, item_id)
        if not item:
            continue
        snapshot.append({
            "id": item_id,
            "title": item.get("title") or "",
            "note": item.get("note") or "",
            "tags": _json_field(item.get("tags")) or [],
        })

    backup_dir = settings.data_dir / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    filename = f"csv-import-{timestamp}.json.lz4"
    payload = json.dumps(snapshot, ensure_ascii=False).encode("utf-8")
    (backup_dir / filename).write_bytes(lz4.frame.compress(payload))

    existing = sorted(backup_dir.glob("csv-import-*.json.lz4"))
    for stale in existing[:-CSV_BACKUP_KEEP]:
        stale.unlink(missing_ok=True)

    return filename


@router.get("")
def list_items(conn: sqlite3.Connection = Depends(get_db), _: str = Depends(require_session)):
    return [_enrich(i) for i in get_all_items(conn)]


@router.get("/export/csv")
def export_csv(
    q: str = "",
    conn: sqlite3.Connection = Depends(get_db),
    _: None = Depends(require_admin),
):
    """Export item metadata as CSV, honoring the same search filter the
    dashboard uses (empty q = all items). title/note/tags are editable on
    re-import; the remaining columns are reference-only."""
    items = search_items(conn, q) if q else get_all_items(conn)
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(CSV_COLUMNS)
    for item in items:
        writer.writerow([
            item.get("id") or "",
            item.get("title") or "",
            item.get("note") or "",
            _tags_to_cell(item.get("tags")),
            item.get("mime_type") or "",
            item.get("ingested_at") or "",
            CSV_TAGS_SEP.join(item.get("collection_ids") or []),
        ])
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="catalogue-metadata-{timestamp}.csv"'},
    )


@router.post("/import/csv/preview")
async def preview_csv_import(
    file: UploadFile = File(...),
    conn: sqlite3.Connection = Depends(get_db),
    _: None = Depends(require_admin),
):
    """Dry run: parse the CSV and report what would change. No writes."""
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="only .csv files are supported")
    data = await file.read()
    return _csv_changes(conn, data)


@router.post("/import/csv")
async def apply_csv_import(
    file: UploadFile = File(...),
    conn: sqlite3.Connection = Depends(get_db),
    _: None = Depends(require_admin),
):
    """Apply title/note/tags changes from the CSV. Takes a compressed backup of
    affected items' current metadata before writing."""
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="only .csv files are supported")
    data = await file.read()
    changes = _csv_changes(conn, data)

    affected = [c["id"] for c in changes["to_update"]]
    backup = _write_csv_backup(conn, affected) if affected else None

    updated: list[str] = []
    for change in changes["to_update"]:
        fields: dict[str, Any] = {}
        if "title" in change:
            fields["title"] = change["title"]["new"]
        if "note" in change:
            fields["note"] = change["note"]["new"]
        if "tags" in change:
            fields["tags"] = change["tags"]["new"]
        if fields:
            update_item_meta(conn, change["id"], fields)
            updated.append(change["id"])

    return {
        "updated": updated,
        "skipped": [s for s in changes["skipped"] if s],
        "unchanged": changes["unchanged"],
        "backup": backup,
    }


DELETE_BACKUP_CONFIRM = "delete metadata backup"


def _backup_dir() -> Path:
    return settings.data_dir / "backups"


@router.get("/import/csv/backups")
def list_csv_backups(_: None = Depends(require_admin)):
    """List the lz4 metadata backups written before CSV imports, newest first."""
    backup_dir = _backup_dir()
    if not backup_dir.exists():
        return {"backups": []}
    backups = []
    for path in sorted(backup_dir.glob("csv-import-*.json.lz4"), reverse=True):
        stat = path.stat()
        backups.append({
            "filename": path.name,
            "size": stat.st_size,
            "created_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(timespec="seconds"),
        })
    return {"backups": backups}


class DeleteBackup(BaseModel):
    confirm: str


@router.delete("/import/csv/backups/{filename}")
def delete_csv_backup(filename: str, body: DeleteBackup, _: None = Depends(require_admin)):
    """Delete a single metadata backup. Requires a typed confirmation phrase
    (GitHub-style) so deletion can't happen by accident."""
    if body.confirm.strip() != DELETE_BACKUP_CONFIRM:
        raise HTTPException(status_code=400, detail=f'type "{DELETE_BACKUP_CONFIRM}" to confirm')
    # Guard against path traversal: only accept the bare expected filename shape.
    if Path(filename).name != filename or not filename.startswith("csv-import-") or not filename.endswith(".json.lz4"):
        raise HTTPException(status_code=400, detail="invalid backup filename")
    target = _backup_dir() / filename
    if not target.exists():
        raise HTTPException(status_code=404, detail="backup not found")
    target.unlink()
    return {"ok": True}


@router.get("/search")
def search_items_endpoint(
    q: str = "",
    conn: sqlite3.Connection = Depends(get_db),
    _: str = Depends(require_session),
):
    """Full-text search across title, note, tags and flattened raw_meta.
    An empty query returns all items, matching list_items behavior."""
    return [_enrich(i) for i in search_items(conn, q)]


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


@router.post("/bulk/favorite")
def bulk_favorite(body: BulkIds, conn: sqlite3.Connection = Depends(get_db), _: None = Depends(require_admin)):
    updated, missing = [], []
    for item_id in body.item_ids:
        if get_item(conn, item_id):
            add_item_to_collection(conn, item_id, "favorites")
            updated.append(item_id)
        else:
            missing.append(item_id)
    return {"updated": updated, "missing": missing}


@router.post("/bulk/unfavorite")
def bulk_unfavorite(body: BulkIds, conn: sqlite3.Connection = Depends(get_db), _: None = Depends(require_admin)):
    updated, missing = [], []
    for item_id in body.item_ids:
        if get_item(conn, item_id):
            remove_item_from_collection(conn, item_id, "favorites")
            updated.append(item_id)
        else:
            missing.append(item_id)
    return {"updated": updated, "missing": missing}


@router.post("/archive")
def bulk_archive_items(body: BulkIds, conn: sqlite3.Connection = Depends(get_db), _: str = Depends(require_session)):
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for item_id in body.item_ids:
            item = get_item(conn, item_id)
            if item:
                root = _library_root(conn, item)
                _write_item_to_zip(zf, item, root, prefix=f"{item_id}/")
    buffer.seek(0)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="items_bulk_{timestamp}.zip"'},
    )


@router.get("/{item_id}")
def get_item_endpoint(item_id: str, conn: sqlite3.Connection = Depends(get_db), _: str = Depends(require_session)):
    item = get_item(conn, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="item not found")
    return _enrich(item)


@router.get("/{item_id}/metadata")
def item_metadata(
    item_id: str,
    request: Request,
    conn: sqlite3.Connection = Depends(get_db),
    _: str = Depends(require_session),
):
    """Machine-readable schema.org/Dublin Core metadata (JSON-LD) for an item.
    The persistent item id is embedded as @id/identifier (FAIR F1+F3). Gated
    behind a session for now; can be exposed publicly for open harvesting later."""
    item = get_item(conn, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="item not found")
    item = _enrich(item)

    base = str(request.base_url).rstrip("/")
    item_url = f"{base}/api/items/{item_id}"
    raw_meta = item.get("raw_meta") or {}

    doc: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "VisualArtwork",
        "@id": item_url,
        "identifier": item_id,
        "name": item.get("title"),
        "description": item.get("note") or None,
        "keywords": item.get("tags") or [],
        "dateModified": item.get("ingested_at"),
        "datePublished": item.get("ingested_at"),
    }
    if item.get("imported_at"):
        doc["dateCreated"] = item["imported_at"]
    if item.get("preview_url"):
        doc["image"] = f"{base}{item['preview_url']}"
    if isinstance(raw_meta, dict) and raw_meta:
        doc["additionalProperty"] = [
            {"@type": "PropertyValue", "name": str(k), "value": v}
            for k, v in raw_meta.items()
        ]

    return Response(
        content=json.dumps(doc, ensure_ascii=False, indent=2),
        media_type="application/ld+json",
    )


def _library_root(conn: sqlite3.Connection, item: dict[str, Any]) -> Path:
    lib = get_library(conn, item.get("library_id"))
    if not lib:
        raise HTTPException(status_code=404, detail="library not found for item")
    root = Path(lib["path"])
    if not root.exists():
        raise HTTPException(status_code=404, detail="library path is not accessible")
    return root


@router.get("/{item_id}/raw/{filename}")
def raw_file(item_id: str, filename: str, conn: sqlite3.Connection = Depends(get_db), _: str = Depends(require_session)):
    item = get_item(conn, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="item not found")
    other_files = _json_field(item.get("other_files"))
    match = next((f for f in other_files if f.lower().endswith(".lz4") and Path(f).name == filename), None)
    if not match:
        raise HTTPException(status_code=404, detail="file not found")
    root = _library_root(conn, item)
    file_path = root / match
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="file not found")
    # Served raw, as stored (no decompression) — download-only.
    return Response(
        content=file_path.read_bytes(),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _write_item_to_zip(zf: zipfile.ZipFile, item: dict[str, Any], root: Path, prefix: str = "") -> None:
    other_files = _json_field(item.get("other_files"))
    if item.get("preview_path"):
        preview_path = root / item["preview_path"]
        if preview_path.exists():
            zf.write(preview_path, f"{prefix}{Path(item['preview_path']).name}")
    for f in other_files:
        file_path = root / f
        if not file_path.exists():
            continue
        if f.lower().endswith(".lz4"):
            zf.writestr(f"{prefix}{Path(f[:-4]).name}", lz4.frame.decompress(file_path.read_bytes()))
        else:
            zf.write(file_path, f"{prefix}{Path(f).name}")


@router.get("/{item_id}/archive")
def archive_item(item_id: str, conn: sqlite3.Connection = Depends(get_db), _: str = Depends(require_session)):
    item = get_item(conn, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="item not found")

    root = _library_root(conn, item)
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        _write_item_to_zip(zf, item, root)
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{item_id}.zip"'},
    )


@router.post("/upload")
async def upload_item(
    file: UploadFile = File(...),
    library_id: Optional[str] = Form(None),
    conn: sqlite3.Connection = Depends(get_db),
    _: None = Depends(require_admin),
):
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="only .zip files are supported")

    data = await file.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail=f"upload exceeds max size of {settings.max_upload_bytes} bytes")

    if library_id:
        lib = get_library(conn, library_id)
        if not lib:
            raise HTTPException(status_code=400, detail="unknown library")
    else:
        lib = get_default_library(conn)
        if not lib:
            raise HTTPException(status_code=500, detail="no default library configured")

    import_dt = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        result = ingest_zip_bytes(
            data,
            file.filename,
            conn,
            lib["id"],
            Path(lib["path"]),
            import_dt=import_dt,
        )
    except ValueError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    return {
        "item": _enrich(result.item) if result.item else None,
        "created": result.created,
        "note": result.note,
    }


class ItemUpdate(BaseModel):
    title: Optional[str] = None
    note: Optional[str] = None
    tags: Optional[list[str]] = None
    collection_ids: Optional[list[str]] = None
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
    collection_ids = fields.pop("collection_ids", None)
    if collection_ids is not None:
        set_item_collections(conn, item_id, collection_ids)
    updated = update_item_meta(conn, item_id, fields)
    return _enrich(updated)


@router.post("/{item_id}/favorite")
def favorite_item(item_id: str, conn: sqlite3.Connection = Depends(get_db), _: None = Depends(require_admin)):
    if not get_item(conn, item_id):
        raise HTTPException(status_code=404, detail="item not found")
    add_item_to_collection(conn, item_id, "favorites")
    return _enrich(get_item(conn, item_id))


@router.delete("/{item_id}/favorite")
def unfavorite_item(item_id: str, conn: sqlite3.Connection = Depends(get_db), _: None = Depends(require_admin)):
    if not get_item(conn, item_id):
        raise HTTPException(status_code=404, detail="item not found")
    remove_item_from_collection(conn, item_id, "favorites")
    return _enrich(get_item(conn, item_id))


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

    root = _library_root(conn, item)
    preview_path = root / item["preview_path"]
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
