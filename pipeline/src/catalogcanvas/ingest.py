from __future__ import annotations
import hashlib
import json
import mimetypes
import subprocess
import tomllib
import zipfile
from pathlib import Path
from typing import Optional

import duckdb
from rich.console import Console

from .config import CatalogConfig
from .convert import to_webp
from .db import hash_exists, upsert_item
from .ids import generate_item_id

# Priority order for selecting which image becomes the webp preview.
PREVIEW_MIME_PRIORITY = ["image/png", "image/jpeg", "image/tiff", "image/svg+xml"]

console = Console()


def _mime_type(name: str) -> Optional[str]:
    mime, _ = mimetypes.guess_type(name)
    if mime == "image/svg" or name.lower().endswith(".svg"):
        return "image/svg+xml"
    return mime


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


def _load_overrides(col_toml_path: Path, content_hash: str, zip_stem: str) -> dict:
    if not col_toml_path.exists():
        return {}
    with open(col_toml_path, "rb") as f:
        data = tomllib.load(f)
    items = data.get("items", {})
    return items.get(content_hash, items.get(zip_stem, {}))


def ingest_zip(
    zip_path: Path,
    conn: duckdb.DuckDBPyConnection,
    cfg: CatalogConfig,
    repo_root: Path,
    col_toml_path: Optional[Path] = None,
    force: bool = False,
    import_dt: Optional[str] = None,
) -> Optional[str]:
    """Ingest a single ZIP file as one item. Returns the item id, or None if skipped."""
    content_hash = hashlib.sha256(zip_path.read_bytes()).hexdigest()

    existing = hash_exists(conn, content_hash)
    if existing and not force:
        return None

    with zipfile.ZipFile(zip_path) as zf:
        members = [
            n for n in zf.namelist()
            if not n.startswith("__MACOSX/") and not n.endswith("/")
        ]

        preview_choice, preview_candidates = _select_preview(members)
        if len(preview_candidates) > 1:
            ext = Path(preview_choice[0]).suffix.lstrip(".")
            console.print(
                f"[dim]note:[/dim] {len(preview_candidates)} {ext} images found in "
                f"{zip_path.name}, using [bold]{preview_choice[0]}[/bold] as preview"
            )

        item_id = existing or generate_item_id(conn)
        items_dir = repo_root / cfg.paths.output_dir / "items" / item_id
        other_dir = items_dir / "other"

        preview_path: Optional[str] = None
        preview_mime: Optional[str] = None
        other_files: list[str] = []
        raw_meta: dict = {}

        for name in members:
            data = zf.read(name)
            base_name = Path(name).name

            if preview_choice and name == preview_choice[0]:
                preview_mime = preview_choice[1]
                out_file = items_dir / "preview.webp"
                to_webp(data, preview_mime, out_file, scale=cfg.build.image_scale)
                preview_path = str(out_file.relative_to(repo_root))
                continue

            if base_name in ("metadata.json", "metadata.toml"):
                try:
                    raw_meta = json.loads(data) if base_name.endswith(".json") else tomllib.loads(data.decode())
                except (json.JSONDecodeError, tomllib.TOMLDecodeError):
                    raw_meta = {}

            other_dir.mkdir(parents=True, exist_ok=True)
            out_file = other_dir / base_name
            out_file.write_bytes(data)

            if cfg.ingest.compress_other_files:
                lz4_path = out_file.with_suffix(out_file.suffix + ".lz4")
                subprocess.run(["lz4", "-9", "-f", str(out_file), str(lz4_path)], check=True, capture_output=True)
                out_file.unlink()
                out_file = lz4_path

            other_files.append(str(out_file.relative_to(repo_root)))

    overrides = _load_overrides(col_toml_path, content_hash, zip_path.stem) if col_toml_path else {}

    record = {
        "id": item_id,
        "content_hash": content_hash,
        "title": overrides.get("title", zip_path.stem),
        "note": overrides.get("note", ""),
        "mime_type": preview_mime,
        "zip_path": str(zip_path.relative_to(repo_root)) if zip_path.is_relative_to(repo_root) else str(zip_path),
        "preview_path": preview_path,
        "other_files": other_files,
        "tags": overrides.get("tags", []),
        "collection_id": overrides.get("collection"),
        "raw_meta": raw_meta,
        "imported_at": import_dt,
    }
    upsert_item(conn, record)
    return item_id
