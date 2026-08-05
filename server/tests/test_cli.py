from __future__ import annotations
import io
import sqlite3
import zipfile
from pathlib import Path

import pytest

from cataloguecanvas import backup as backup_mod
from cataloguecanvas import cli, db
from cataloguecanvas.auth import pwd_context
from cataloguecanvas.settings import settings


@pytest.fixture()
def data_dir(tmp_path, monkeypatch):
    """Redirect the whole app data dir at a per-test tree."""
    root = tmp_path / "data"
    storage = root / "storage"
    monkeypatch.setattr(settings, "data_dir", root)
    monkeypatch.setattr(settings, "db_path", root / "catalogue.db")
    monkeypatch.setattr(settings, "storage_dir", storage)
    monkeypatch.setattr(settings, "audit_log_path", root / "logs" / "audit.log")
    monkeypatch.setattr(settings, "audit_log_enabled", True)
    root.mkdir(parents=True, exist_ok=True)
    storage.mkdir(parents=True, exist_ok=True)
    return root


def _seed_db():
    conn = db.get_connection(settings.db_path)
    db.ensure_schema(conn)
    return conn


# --- parser ---

def test_parser_requires_a_subcommand():
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args([])


@pytest.mark.parametrize("command", ["reset-password", "backup", "restore", "ingest", "diagnostics"])
def test_all_subcommands_registered(command):
    # `restore` and `ingest` take a positional argument.
    argv = [command] + (["x"] if command in ("restore", "ingest") else [])
    args = cli.build_parser().parse_args(argv)
    assert args.command == command
    assert callable(args.func)


# --- reset-password ---

def test_reset_password_sets_admin_hash(data_dir, capsys):
    conn = _seed_db()
    conn.close()

    rc = cli.main(["reset-password", "--user", settings.admin_username, "--password", "newpass123"])
    assert rc == 0

    conn = db.get_connection(settings.db_path)
    try:
        assert pwd_context.verify("newpass123", db.get_admin_hash(conn))
    finally:
        conn.close()
    assert "Password updated" in capsys.readouterr().out


def test_reset_password_revokes_sessions(data_dir, capsys):
    conn = _seed_db()
    db.create_session(conn, "sid-1", "admin", "admin")
    db.create_session(conn, "sid-2", "reader", "bob")
    conn.close()

    assert cli.main(["reset-password", "--password", "newpass123"]) == 0

    conn = db.get_connection(settings.db_path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 0
    finally:
        conn.close()
    assert "Revoked 2 active session(s)" in capsys.readouterr().out


def test_reset_password_updates_named_user(data_dir):
    conn = _seed_db()
    db.create_user(conn, "bob", pwd_context.hash("old"), "reader")
    conn.close()

    assert cli.main(["reset-password", "--user", "bob", "--password", "brandnew"]) == 0

    conn = db.get_connection(settings.db_path)
    try:
        user = db.get_user_by_username(conn, "bob")
        assert pwd_context.verify("brandnew", user["password_hash"])
    finally:
        conn.close()


def test_reset_password_unknown_user_fails(data_dir, capsys):
    conn = _seed_db()
    conn.close()

    assert cli.main(["reset-password", "--user", "nobody", "--password", "x"]) == 1
    assert "no such user" in capsys.readouterr().err


def test_reset_password_rejects_empty(data_dir, capsys):
    conn = _seed_db()
    conn.close()
    assert cli.main(["reset-password", "--password", ""]) == 1
    assert "cannot be empty" in capsys.readouterr().err


# --- backup ---

def test_backup_writes_archive(data_dir, capsys):
    conn = _seed_db()
    lib = db.get_default_library(conn)
    item_file = Path(lib["path"]) / "items" / "abc" / "preview.webp"
    item_file.parent.mkdir(parents=True, exist_ok=True)
    item_file.write_bytes(b"fake-webp")
    conn.close()

    out = data_dir / "backups" / "test.zip"
    assert cli.main(["backup", "--out", str(out)]) == 0
    assert out.is_file()

    with zipfile.ZipFile(out) as zf:
        names = zf.namelist()
    assert backup_mod.DB_ARCNAME in names
    assert any(n.startswith("storage/") and n.endswith("preview.webp") for n in names)
    assert "Backup written" in capsys.readouterr().out


def test_backup_to_directory_generates_filename(data_dir):
    conn = _seed_db()
    conn.close()

    out_dir = data_dir / "backups"
    out_dir.mkdir(parents=True, exist_ok=True)
    assert cli.main(["backup", "--out", str(out_dir)]) == 0
    assert list(out_dir.glob("cataloguecanvas-backup-*.zip"))


# --- restore ---

def _make_backup(data_dir) -> Path:
    conn = _seed_db()
    lib = db.get_default_library(conn)
    db.upsert_item(conn, {
        "id": "kept-001",
        "content_hash": "hash-kept",
        "title": "Kept",
        "library_id": lib["id"],
    })
    out = data_dir / "backup.zip"
    backup_mod.create_backup(conn, out)
    conn.close()
    return out


def test_restore_replaces_database(data_dir, capsys):
    archive = _make_backup(data_dir)

    # Wipe the DB so the restore has something to put back.
    settings.db_path.unlink()
    assert cli.main(["restore", str(archive), "--force"]) == 0

    conn = db.get_connection(settings.db_path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM items").fetchone()[0] == 1
    finally:
        conn.close()
    assert "Restored" in capsys.readouterr().out


def test_restore_refuses_populated_db_without_force(data_dir, capsys):
    archive = _make_backup(data_dir)
    # The seeded DB still holds the item, so a restore would overwrite data.
    assert cli.main(["restore", str(archive)]) == 1
    assert "refusing to restore" in capsys.readouterr().err


def test_restore_keeps_previous_database(data_dir, capsys):
    archive = _make_backup(data_dir)
    assert cli.main(["restore", str(archive), "--force"]) == 0
    assert list(settings.db_path.parent.glob("catalogue.db.pre-restore-*"))
    assert "Previous database kept at" in capsys.readouterr().out


def test_restore_missing_archive(data_dir, capsys):
    assert cli.main(["restore", str(data_dir / "nope.zip")]) == 1
    assert "archive not found" in capsys.readouterr().err


def test_restore_rejects_non_zip(data_dir, capsys):
    bogus = data_dir / "bogus.zip"
    bogus.write_text("definitely not a zip")
    assert cli.main(["restore", str(bogus)]) == 1
    assert "not a valid zip" in capsys.readouterr().err


def test_restore_rejects_archive_without_database(data_dir, capsys):
    archive = data_dir / "nodb.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("storage/lib-1/file.txt", "x")
    assert cli.main(["restore", str(archive)]) == 1
    assert "does not contain catalogue.db" in capsys.readouterr().err


def test_inspect_archive_rejects_traversal(data_dir):
    archive = data_dir / "evil.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr(backup_mod.DB_ARCNAME, "x")
        zf.writestr("storage/../../../etc/passwd", "pwned")

    with pytest.raises(backup_mod.RestoreError, match="unsafe path"):
        backup_mod.inspect_archive(archive)


def test_inspect_archive_rejects_absolute_path(data_dir):
    archive = data_dir / "abs.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr(backup_mod.DB_ARCNAME, "x")
        zf.writestr("/etc/shadow", "pwned")

    with pytest.raises(backup_mod.RestoreError, match="unsafe path"):
        backup_mod.inspect_archive(archive)


def test_inspect_archive_rejects_symlink(data_dir):
    archive = data_dir / "link.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr(backup_mod.DB_ARCNAME, "x")
        info = zipfile.ZipInfo("storage/lib-1/link")
        # 0o120000 in the top bits marks a symlink entry.
        info.external_attr = (0o120777 << 16)
        zf.writestr(info, "/etc/passwd")

    with pytest.raises(backup_mod.RestoreError, match="symlink"):
        backup_mod.inspect_archive(archive)


# --- ingest ---

def _zip_bytes(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()


def test_ingest_missing_directory(data_dir, capsys):
    assert cli.main(["ingest", str(data_dir / "absent")]) == 1
    assert "not a directory" in capsys.readouterr().err


def test_ingest_empty_directory(data_dir, capsys):
    conn = _seed_db()
    conn.close()
    src = data_dir / "import"
    src.mkdir()
    assert cli.main(["ingest", str(src)]) == 0
    assert "No .zip files found" in capsys.readouterr().out


def test_ingest_unknown_library(data_dir, capsys):
    conn = _seed_db()
    conn.close()
    src = data_dir / "import"
    src.mkdir()
    (src / "a.zip").write_bytes(_zip_bytes({"a.txt": b"hello"}))

    assert cli.main(["ingest", str(src), "--library", "lib-nope"]) == 1
    assert "unknown library" in capsys.readouterr().err


def test_ingest_creates_items(data_dir, capsys):
    conn = _seed_db()
    conn.close()
    src = data_dir / "import"
    src.mkdir()
    (src / "one.zip").write_bytes(_zip_bytes({"notes.txt": b"first"}))
    (src / "two.zip").write_bytes(_zip_bytes({"notes.txt": b"second"}))

    assert cli.main(["ingest", str(src)]) == 0
    out = capsys.readouterr().out
    assert "2 created" in out

    conn = db.get_connection(settings.db_path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM items").fetchone()[0] == 2
    finally:
        conn.close()


def test_ingest_skips_duplicates(data_dir, capsys):
    conn = _seed_db()
    conn.close()
    src = data_dir / "import"
    src.mkdir()
    payload = _zip_bytes({"notes.txt": b"same"})
    (src / "first.zip").write_bytes(payload)
    (src / "second.zip").write_bytes(payload)

    assert cli.main(["ingest", str(src)]) == 0
    out = capsys.readouterr().out
    assert "1 created" in out
    assert "1 skipped" in out


# --- diagnostics ---

def test_diagnostics_writes_to_file(data_dir, capsys):
    conn = _seed_db()
    conn.close()
    out = data_dir / "report.md"
    assert cli.main(["diagnostics", "--out", str(out)]) == 0
    assert "CatalogueCanvas Diagnostic Report" in out.read_text()


def test_diagnostics_prints_to_stdout(data_dir, capsys):
    conn = _seed_db()
    conn.close()
    assert cli.main(["diagnostics"]) == 0
    assert "CatalogueCanvas Diagnostic Report" in capsys.readouterr().out


# --- backup helpers ---

def test_current_item_count_without_database(data_dir):
    if settings.db_path.exists():
        settings.db_path.unlink()
    assert backup_mod.current_item_count() == 0


def test_current_item_count_with_items(data_dir):
    conn = _seed_db()
    lib = db.get_default_library(conn)
    db.upsert_item(conn, {
        "id": "x-1", "content_hash": "h1", "title": "T", "library_id": lib["id"],
    })
    conn.close()
    assert backup_mod.current_item_count() == 1


def test_current_item_count_on_schemaless_file(data_dir):
    # A database file with no `items` table must read as empty, not explode.
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    sqlite3.connect(str(settings.db_path)).close()
    assert backup_mod.current_item_count() == 0
