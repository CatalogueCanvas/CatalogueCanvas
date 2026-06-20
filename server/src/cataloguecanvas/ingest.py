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
from .settings import settings

# Priority order for selecting which image becomes the webp preview.
PREVIEW_MIME_PRIORITY = ["image/png", "image/jpeg", "image/tiff", "image/svg+xml"]

# OS/editor noise that should never be stored as an item file.
NOISE_BASENAMES = {".ds_store", "thumbs.db", "thumbnails.db", "desktop.ini"}


def _mime_type(name: str) -> Optional[str]:
    mime, _ = mimetypes.guess_type(name)
    if mime == "image/svg" or name.lower().endswith(".svg"):
        return "image/svg+xml"
    return mime


def _unique_name(other_dir: Path, name: str) -> str:
    """Return `name`, or a de-duplicated variant if a file with that name already
    exists in other_dir (collision from flattening ZIP subfolders)."""
    if not (other_dir / name).exists():
        return name
    stem, suffix = Path(name).stem, Path(name).suffix
    i = 1
    while (other_dir / f"{stem}_{i}{suffix}").exists():
        i += 1
    return f"{stem}_{i}{suffix}"


def _write_other_file(other_dir: Path, base_name: str, data: bytes, library_path: Path) -> str:
    """Write a file into other_dir, lz4-compressing SVGs, and return its
    library-relative path. De-duplicates basenames that collide after flattening."""
    other_dir.mkdir(parents=True, exist_ok=True)
    if base_name.lower().endswith(".svg"):
        target = _unique_name(other_dir, f"{base_name}.lz4")
        out_file = other_dir / target
        out_file.write_bytes(lz4.frame.compress(data))
    else:
        target = _unique_name(other_dir, base_name)
        out_file = other_dir / target
        out_file.write_bytes(data)
    return str(out_file.relative_to(library_path))


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
    library_id: str,
    library_path: Path,
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
        if len(zf.namelist()) > settings.max_zip_entries:
            raise ValueError(f"zip has more than {settings.max_zip_entries} entries")

        members = [
            n for n in zf.namelist()
            if not n.startswith("__MACOSX/")
            and not n.endswith("/")
            and Path(n).name.lower() not in NOISE_BASENAMES
        ]

        total_size = 0
        for name in members:
            info = zf.getinfo(name)
            if info.file_size > settings.max_zip_member_bytes:
                raise ValueError(f"member {name!r} exceeds max size of {settings.max_zip_member_bytes} bytes")
            total_size += info.file_size
        if total_size > settings.max_zip_total_bytes:
            raise ValueError(f"zip total uncompressed size exceeds {settings.max_zip_total_bytes} bytes")

        preview_choice, preview_candidates = _select_preview(members)
        if len(preview_candidates) > 1:
            ext = Path(preview_choice[0]).suffix.lstrip(".")
            note = (
                f"{len(preview_candidates)} {ext} images found; "
                f"using {preview_choice[0]} as preview"
            )

        item_id = existing or generate_item_id(conn)
        items_dir = library_path / "items" / item_id
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
                preview_path = str(out_file.relative_to(library_path))
                with Image.open(out_file) as img:
                    preview_width, preview_height = img.size
                if preview_mime == "image/svg+xml":
                    other_files.append(_write_other_file(other_dir, base_name, member_data, library_path))
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

            other_files.append(_write_other_file(other_dir, base_name, member_data, library_path))
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
        "raw_meta": raw_meta,
        "imported_at": import_dt,
        "library_id": library_id,
    }
    upsert_item(conn, record)
    return IngestResult(item=get_item(conn, item_id), created=True, note=note)
