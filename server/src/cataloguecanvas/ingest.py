from __future__ import annotations
import hashlib
import json
import mimetypes
import sqlite3
import tomllib
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Optional

import lz4.frame
from PIL import Image

from .convert import to_webp
from .db import hash_exists, upsert_item, get_item
from .ids import generate_item_id

# Priority order for selecting which image becomes the webp preview.
PREVIEW_MIME_PRIORITY = ["image/png", "image/jpeg", "image/tiff", "image/svg+xml"]


def _mime_type(name: str) -> Optional[str]:
    mime, _ = mimetypes.guess_type(name)
    if mime == "image/svg" or name.lower().endswith(".svg"):
        return "image/svg+xml"
    return mime


def _write_other_file(other_dir: Path, base_name: str, data: bytes, storage_dir: Path) -> str:
    """Write a file into other_dir, lz4-compressing SVGs, and return its
    storage-relative path."""
    other_dir.mkdir(parents=True, exist_ok=True)
    if base_name.lower().endswith(".svg"):
        out_file = other_dir / f"{base_name}.lz4"
        out_file.write_bytes(lz4.frame.compress(data))
    else:
        out_file = other_dir / base_name
        out_file.write_bytes(data)
    return str(out_file.relative_to(storage_dir))


def _select_preview(members: list[str]) -> tuple[Optional[tuple[str, str]], list[str]]:
    """Return ((member_name, mime_type), all_candidate_names_for_that_mime) for the
    chosen preview image, or (None, []) if no image is found."""
    candidates: dict[str, list[str]] = {}
    for name in members:
        mime = _mime_type(name)
        if mime in PREVIEW_MIME_PRIORITY:
            candidates.setdefault(mime, []).append(name)
    for mime in PREVIEW_MIME_PRIORITY:
        if mime in candidates:
            return (candidates[mime][0], mime), candidates[mime]
    return None, []


class IngestResult:
    def __init__(self, item: Optional[dict], created: bool, note: Optional[str] = None):
        self.item = item
        self.created = created
        self.note = note


def ingest_zip_bytes(
    data: bytes,
    filename: str,
    conn: sqlite3.Connection,
    storage_dir: Path,
    image_scale: float = 2.5,
    force: bool = False,
    import_dt: Optional[str] = None,
) -> IngestResult:
    """Ingest a single ZIP file's bytes as one item.

    Returns an IngestResult with `item` (the upserted item record), `created`
    (False if skipped/deduplicated by content hash and not forced), and an
    optional human-readable `note`.
    """
    content_hash = hashlib.sha256(data).hexdigest()

    existing = hash_exists(conn, content_hash)
    if existing and not force:
        return IngestResult(item=get_item(conn, existing), created=False, note="already ingested")

    note: Optional[str] = None
    zip_stem = Path(filename).stem

    with zipfile.ZipFile(BytesIO(data)) as zf:
        members = [
            n for n in zf.namelist()
            if not n.startswith("__MACOSX/") and not n.endswith("/")
        ]

        preview_choice, preview_candidates = _select_preview(members)
        if len(preview_candidates) > 1:
            ext = Path(preview_choice[0]).suffix.lstrip(".")
            note = (
                f"{len(preview_candidates)} {ext} images found; "
                f"using {preview_choice[0]} as preview"
            )

        item_id = existing or generate_item_id(conn)
        items_dir = storage_dir / "items" / item_id
        other_dir = items_dir / "other"

        preview_path: Optional[str] = None
        preview_mime: Optional[str] = None
        preview_width: Optional[int] = None
        preview_height: Optional[int] = None
        other_files: list[str] = []
        raw_meta: dict = {}
        svg_compressed = False

        for name in members:
            member_data = zf.read(name)
            base_name = Path(name).name

            if preview_choice and name == preview_choice[0]:
                preview_mime = preview_choice[1]
                out_file = items_dir / "preview.webp"
                to_webp(member_data, preview_mime, out_file, scale=image_scale)
                preview_path = str(out_file.relative_to(storage_dir))
                with Image.open(out_file) as img:
                    preview_width, preview_height = img.size
                if preview_mime == "image/svg+xml":
                    other_files.append(_write_other_file(other_dir, base_name, member_data, storage_dir))
                    svg_compressed = True
                continue

            if base_name in ("metadata.json", "metadata.toml"):
                try:
                    raw_meta = (
                        json.loads(member_data)
                        if base_name.endswith(".json")
                        else tomllib.loads(member_data.decode())
                    )
                except (json.JSONDecodeError, tomllib.TOMLDecodeError):
                    raw_meta = {}

            other_files.append(_write_other_file(other_dir, base_name, member_data, storage_dir))
            if base_name.lower().endswith(".svg"):
                svg_compressed = True

    if svg_compressed:
        compress_note = "SVG compressed (lz4)"
        note = f"{note}; {compress_note}" if note else compress_note

    record = {
        "id": item_id,
        "content_hash": content_hash,
        "title": zip_stem,
        "note": "",
        "mime_type": preview_mime,
        "preview_path": preview_path,
        "width": preview_width,
        "height": preview_height,
        "other_files": other_files,
        "tags": [],
        "collection_id": None,
        "raw_meta": raw_meta,
        "imported_at": import_dt,
    }
    upsert_item(conn, record)
    return IngestResult(item=get_item(conn, item_id), created=True, note=note)
