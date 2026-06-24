from __future__ import annotations

from cataloguecanvas import db, diagnostics
from cataloguecanvas.settings import settings


# --- pure helpers ---

def test_fmt_bytes():
    assert diagnostics._fmt_bytes(0) == "0 B"
    assert diagnostics._fmt_bytes(1024) == "1.0 KiB"
    assert diagnostics._fmt_bytes(1024 ** 3) == "1.0 GiB"


def test_pkg_version_known_and_unknown():
    assert diagnostics._pkg_version("pytest") != "not installed"
    assert diagnostics._pkg_version("definitely-not-a-real-pkg-xyz") == "not installed"


def test_dir_size(tmp_path):
    (tmp_path / "a.txt").write_bytes(b"x" * 100)
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.txt").write_bytes(b"y" * 50)
    assert diagnostics._dir_size(tmp_path) == 150


def test_app_version_returns_string():
    assert isinstance(diagnostics._app_version(), str)


# --- full report ---

def test_build_report_renders_all_sections(app_conn):
    # Seed a little data so the DB section has something to count.
    db.upsert_item(app_conn, {
        "id": "diag-1", "content_hash": "hd1", "title": "T",
        "library_id": db.get_default_library(app_conn)["id"],
    })
    report = diagnostics.build_report()
    assert "# CatalogueCanvas Diagnostic Report" in report
    for heading in ("## Versions", "## Configuration", "## Disk & storage",
                    "## LLM", "## Database", "## Storage integrity"):
        assert heading in report
    # secrets are never echoed verbatim
    assert settings.secret_key not in report
