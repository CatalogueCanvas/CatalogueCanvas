"""Generate a redacted diagnostic report for GitHub issue evaluation.

Collects runtime versions, masked configuration, database counts, and library
path health into a single Markdown report. Secrets (passwords, session keys)
are never included.

Usage:
    uv run python scripts/diagnostics.py            # print to stdout
    uv run python scripts/diagnostics.py report.md  # also write to a file
"""
from __future__ import annotations
import os
import platform
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path

if "CC_DATA_DIR" not in os.environ:
    default_data_dir = Path(__file__).resolve().parents[2] / "data"
    if default_data_dir.is_dir():
        os.environ["CC_DATA_DIR"] = str(default_data_dir)

from cataloguecanvas.settings import settings

_TRACKED_PACKAGES = (
    "fastapi",
    "uvicorn",
    "pydantic",
    "passlib",
    "argon2-cffi",
    "itsdangerous",
    "pillow",
    "cairosvg",
    "lz4",
)


def _pkg_version(name: str) -> str:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return "not installed"


def _app_version() -> str:
    try:
        return metadata.version("cataloguecanvas")
    except metadata.PackageNotFoundError:
        pass
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    try:
        for line in pyproject.read_text().splitlines():
            if line.strip().startswith("version"):
                return line.split("=", 1)[1].strip().strip('"')
    except OSError:
        pass
    return "unknown"


def _node_version() -> str:
    node = shutil.which("node")
    if not node:
        return "not found"
    try:
        return subprocess.run([node, "--version"], capture_output=True, text=True, timeout=5).stdout.strip()
    except (subprocess.SubprocessError, OSError):
        return "error"


def _git_describe() -> str:
    repo = Path(__file__).resolve().parents[2]
    try:
        out = subprocess.run(
            ["git", "describe", "--tags", "--always", "--dirty"],
            cwd=repo, capture_output=True, text=True, timeout=5,
        )
        return out.stdout.strip() or "unknown"
    except (subprocess.SubprocessError, OSError):
        return "unknown"


def _db_section() -> list[str]:
    lines: list[str] = []
    db_path = settings.db_path
    if not db_path.is_file():
        return [f"- Database file: `{db_path}` **(missing)**"]

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        def count(sql: str) -> int:
            try:
                return conn.execute(sql).fetchone()[0]
            except sqlite3.Error:
                return -1

        lines.append(f"- Database file: `{db_path}` ({db_path.stat().st_size:,} bytes)")
        lines.append(f"- Items: {count('SELECT COUNT(*) FROM items')}")
        lines.append(f"- Items missing preview: {count('SELECT COUNT(*) FROM items WHERE preview_path IS NULL OR preview_path = \"\"')}")
        lines.append(f"- Collections: {count('SELECT COUNT(*) FROM collections')}")
        lines.append(f"- Portfolios: {count('SELECT COUNT(*) FROM portfolios')}")
        lines.append(f"- Users: {count('SELECT COUNT(*) FROM users')}")

        try:
            multi = conn.execute(
                "SELECT value FROM app_settings WHERE key = 'multi_user_enabled'"
            ).fetchone()
            lines.append(f"- Multi-user mode: {(multi['value'] if multi else 'false')}")
        except sqlite3.Error:
            pass

        try:
            libs = conn.execute(
                "SELECT id, name, path, is_default FROM libraries ORDER BY is_default DESC, name"
            ).fetchall()
            lines.append("")
            lines.append("### Libraries")
            if not libs:
                lines.append("- (none)")
            for lib in libs:
                path_ok = Path(lib["path"]).is_dir()
                default = " (default)" if lib["is_default"] else ""
                status = "ok" if path_ok else "**MISSING**"
                lines.append(f"- `{lib['name']}`{default}: `{lib['path']}` — {status}")
        except sqlite3.Error:
            pass
    finally:
        conn.close()
    return lines


def build_report() -> str:
    secret_source = "CC_SECRET_KEY_FILE" if os.environ.get("CC_SECRET_KEY_FILE") else "CC_SECRET_KEY"
    secret_is_default = settings.secret_key == "dev-secret-change-me"

    out: list[str] = []
    out.append("# CatalogueCanvas Diagnostic Report")
    out.append("")
    out.append(f"Generated: {datetime.now(timezone.utc).isoformat()}")
    out.append("")

    out.append("## Versions")
    out.append(f"- App version: {_app_version()}")
    out.append(f"- Git describe: {_git_describe()}")
    out.append(f"- Python: {platform.python_version()} ({sys.implementation.name})")
    out.append(f"- Node: {_node_version()}")
    out.append(f"- Platform: {platform.platform()}")
    out.append("")
    out.append("### Python packages")
    for name in _TRACKED_PACKAGES:
        out.append(f"- {name}: {_pkg_version(name)}")
    out.append("")

    out.append("## Configuration (secrets redacted)")
    out.append(f"- Site title: {settings.site_title}")
    out.append(f"- Site author: {settings.site_author or '(empty)'}")
    out.append(f"- Admin username: {settings.admin_username}")
    out.append(f"- Admin password set: {bool(settings.admin_password)}")
    out.append(f"- Secret key source: {secret_source}")
    out.append(f"- Secret key is default: {secret_is_default}")
    out.append(f"- Cookie secure: {settings.cookie_secure}")
    out.append(f"- Data dir: `{settings.data_dir}` (exists: {settings.data_dir.is_dir()})")
    out.append(f"- Storage dir: `{settings.storage_dir}` (exists: {settings.storage_dir.is_dir()})")
    out.append(f"- Static dir: `{settings.static_dir}` (exists: {settings.static_dir.is_dir()})")
    out.append(f"- Max upload bytes: {settings.max_upload_bytes:,}")
    out.append(f"- Max zip member bytes: {settings.max_zip_member_bytes:,}")
    out.append(f"- Max zip total bytes: {settings.max_zip_total_bytes:,}")
    out.append("")

    out.append("## Database")
    out.extend(_db_section())
    out.append("")

    return "\n".join(out)


def main() -> None:
    report = build_report()
    print(report)
    if len(sys.argv) > 1:
        target = Path(sys.argv[1])
        target.write_text(report)
        print(f"\nWritten to {target}", file=sys.stderr)


if __name__ == "__main__":
    main()
