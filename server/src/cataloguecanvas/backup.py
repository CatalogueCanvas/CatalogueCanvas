"""Create and restore full backups (database + library files).

Shared by the admin endpoint (``POST /api/settings/export/all``) and the
``cc backup`` / ``cc restore`` CLI commands so both produce and consume exactly
the same archive layout:

    catalogue.db
    storage/<library_id>/<files...>

Restore is deliberately conservative: it validates the archive first, refuses to
overwrite a populated database unless forced, and moves the existing database
aside instead of deleting it.
"""
from __future__ import annotations
import os
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .db import get_all_libraries
from .settings import settings

DB_ARCNAME = "catalogue.db"
STORAGE_PREFIX = "storage/"


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def create_backup(conn: sqlite3.Connection, out_path: Path) -> Path:
    """Write a backup zip to ``out_path`` and return it.

    ``VACUUM INTO`` gives a consistent snapshot of the live database without
    stopping the server; library files are then added under ``storage/<id>/``.
    Symlinks are skipped so a link planted in a library can't pull an arbitrary
    host file into the archive.
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp_path = Path(tmp.name)
    tmp.close()

    db_conn = sqlite3.connect(str(settings.db_path))
    try:
        db_conn.execute("VACUUM INTO ?", (str(tmp_path),))
    finally:
        db_conn.close()

    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(tmp_path, DB_ARCNAME)
            for lib in get_all_libraries(conn):
                lib_root = Path(lib["path"])
                if not lib_root.exists():
                    continue
                lib_root = lib_root.resolve()
                for path in lib_root.rglob("*"):
                    if path.is_symlink() or not path.is_file():
                        continue
                    resolved = path.resolve()
                    if resolved != lib_root and not str(resolved).startswith(str(lib_root) + os.sep):
                        continue
                    zf.write(path, Path("storage") / lib["id"] / path.relative_to(lib_root))
    finally:
        tmp_path.unlink(missing_ok=True)

    return out_path


def default_backup_path() -> Path:
    return settings.data_dir / "backups" / f"cataloguecanvas-backup-{_timestamp()}.zip"


class RestoreError(Exception):
    """Raised when an archive is unusable or a restore would be unsafe."""


def inspect_archive(archive: Path) -> dict:
    """Validate the archive and summarise what a restore would write.

    Rejects path traversal, absolute members, and symlink entries before
    anything is extracted, using the same limits ingest applies to uploads.
    """
    if not archive.is_file():
        raise RestoreError(f"archive not found: {archive}")

    try:
        with zipfile.ZipFile(archive) as zf:
            names = zf.namelist()
            if len(names) > settings.max_zip_entries:
                raise RestoreError(f"archive has more than {settings.max_zip_entries} entries")

            if DB_ARCNAME not in names:
                raise RestoreError(f"archive does not contain {DB_ARCNAME}")

            storage_files = 0
            total_size = 0
            for info in zf.infolist():
                name = info.filename
                if name.endswith("/"):
                    continue
                # Reject anything that would escape the destination root.
                if name.startswith("/") or ".." in Path(name).parts:
                    raise RestoreError(f"unsafe path in archive: {name}")
                # Symlinks are stored with their type in the high bits of
                # external_attr; extracting one would let the archive plant a
                # link pointing anywhere on the host.
                if (info.external_attr >> 16) & 0o170000 == 0o120000:
                    raise RestoreError(f"archive contains a symlink: {name}")
                if info.file_size > settings.max_zip_member_bytes:
                    raise RestoreError(f"member {name!r} exceeds max size of {settings.max_zip_member_bytes} bytes")
                total_size += info.file_size
                if name.startswith(STORAGE_PREFIX):
                    storage_files += 1
    except zipfile.BadZipFile as exc:
        raise RestoreError(f"not a valid zip archive: {archive}") from exc

    return {"storage_files": storage_files, "total_bytes": total_size, "entries": len(names)}


def current_item_count() -> int:
    """Item count in the live database, or 0 when there is no database yet."""
    if not settings.db_path.is_file():
        return 0
    conn = sqlite3.connect(str(settings.db_path))
    try:
        return int(conn.execute("SELECT COUNT(*) FROM items").fetchone()[0])
    except sqlite3.Error:
        # No schema yet (or an unreadable file): treat as empty so a first-time
        # restore isn't blocked by a stub database.
        return 0
    finally:
        conn.close()


def restore_backup(archive: Path, target_library_root: Optional[Path] = None) -> dict:
    """Extract ``archive`` over the configured data dir.

    The existing database is renamed to ``catalogue.db.pre-restore-<ts>`` rather
    than overwritten, so a mistaken restore is recoverable. Storage files land in
    ``target_library_root`` (default: the configured storage dir), keyed by the
    library id recorded in the archive.

    Callers are responsible for confirming with the user first; this function
    performs the restore unconditionally.
    """
    info = inspect_archive(archive)
    storage_root = target_library_root or settings.storage_dir

    free = shutil.disk_usage(settings.data_dir).free
    if info["total_bytes"] > free:
        raise RestoreError(f"not enough disk space: need {info['total_bytes']} bytes, {free} available")

    settings.ensure_dirs()

    moved_to: Optional[Path] = None
    if settings.db_path.is_file():
        moved_to = settings.db_path.with_name(f"{settings.db_path.name}.pre-restore-{_timestamp()}")
        os.replace(settings.db_path, moved_to)

    extracted = 0
    with zipfile.ZipFile(archive) as zf:
        for info_member in zf.infolist():
            name = info_member.filename
            if name.endswith("/"):
                continue
            if name == DB_ARCNAME:
                dest = settings.db_path
            elif name.startswith(STORAGE_PREFIX):
                dest = storage_root / name[len(STORAGE_PREFIX):]
            else:
                continue

            # Second traversal check against the resolved destination: the name
            # check in inspect_archive guards the archive, this guards the write.
            root = settings.db_path.parent if name == DB_ARCNAME else storage_root
            resolved_root = root.resolve()
            dest.parent.mkdir(parents=True, exist_ok=True)
            if not str(dest.resolve()).startswith(str(resolved_root)):
                raise RestoreError(f"unsafe destination for {name}")

            with zf.open(info_member) as src, dest.open("wb") as out:
                shutil.copyfileobj(src, out)
            extracted += 1

    return {
        "extracted": extracted,
        "previous_db": str(moved_to) if moved_to else None,
        "storage_root": str(storage_root),
    }
