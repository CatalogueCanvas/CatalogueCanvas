"""Build a redacted diagnostic report for GitHub issue evaluation.

Collects runtime versions, masked configuration, database counts, and library
path health into a single Markdown report. Secrets (passwords, session keys)
are never included — only whether they are set and their source.

Used by the `GET /api/settings/diagnostics` admin endpoint and the
`scripts/diagnostics.py` CLI.
"""
from __future__ import annotations
import json
import os
import platform
import shutil
import socket
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from urllib.parse import urlparse

from .settings import settings

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

# Repo root and server dir, derived from this module's location:
# .../server/src/cataloguecanvas/diagnostics.py
_SERVER_DIR = Path(__file__).resolve().parents[2]
_REPO_DIR = _SERVER_DIR.parent


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
    pyproject = _SERVER_DIR / "pyproject.toml"
    try:
        for line in pyproject.read_text().splitlines():
            if line.strip().startswith("version"):
                return line.split("=", 1)[1].strip().strip('"')
    except OSError:
        pass
    return "unknown"


def _git_sha() -> str:
    # Prefer the SHA baked at image build time (no .git in the container).
    if settings.git_sha and settings.git_sha != "unknown":
        return settings.git_sha
    try:
        out = subprocess.run(
            ["git", "describe", "--tags", "--always", "--dirty"],
            cwd=_REPO_DIR, capture_output=True, text=True, timeout=5,
        )
        return out.stdout.strip() or "unknown"
    except (subprocess.SubprocessError, OSError):
        return "unknown"


def _fmt_bytes(n: int) -> str:
    step = 1024.0
    val = float(n)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if val < step:
            return f"{val:.1f} {unit}" if unit != "B" else f"{int(val)} B"
        val /= step
    return f"{val:.1f} PiB"


def _dir_size(path: Path) -> int:
    total = 0
    try:
        for p in path.rglob("*"):
            if p.is_file():
                try:
                    total += p.stat().st_size
                except OSError:
                    pass
    except OSError:
        pass
    return total


def _disk_section() -> list[str]:
    lines: list[str] = []
    data_dir = settings.data_dir
    try:
        usage = shutil.disk_usage(data_dir)
        pct = (usage.used / usage.total * 100) if usage.total else 0
        lines.append(f"- Data volume: {_fmt_bytes(usage.free)} free of {_fmt_bytes(usage.total)} ({pct:.0f}% used)")
    except OSError as exc:
        lines.append(f"- Data volume: could not stat `{data_dir}`: {exc}")
    if settings.storage_dir.is_dir():
        lines.append(f"- Storage dir size: {_fmt_bytes(_dir_size(settings.storage_dir))}")
    if settings.db_path.is_file():
        lines.append(f"- Database size: {_fmt_bytes(settings.db_path.stat().st_size)}")
    return lines


def _llm_section() -> list[str]:
    """Report LLM config (no secrets) and probe reachability of the endpoint."""
    lines: list[str] = []
    db_path = settings.db_path
    if not db_path.is_file():
        return ["- (no database — LLM settings unavailable)"]

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("SELECT key, value FROM app_settings").fetchall()
        cfg = {r["key"]: r["value"] for r in rows}
    except sqlite3.Error:
        cfg = {}
    finally:
        conn.close()

    api_url = cfg.get("llm_api_url", "")
    lines.append(f"- API URL: {api_url or '(not set)'}")
    lines.append(f"- Model: {cfg.get('llm_model') or '(not set)'}")
    lines.append(f"- Auto-generate: {cfg.get('llm_auto_generate', 'false')}")

    if api_url:
        lines.append(f"- Endpoint reachability: {_probe_url(api_url)}")
    return lines


def _probe_url(api_url: str) -> str:
    """Resolve and attempt a TCP connection to the LLM host:port. No request sent."""
    parsed = urlparse(api_url)
    host = parsed.hostname
    if not host:
        return "invalid URL (no host)"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        return f"DNS resolution failed for {host}: {exc}"
    family, socktype, proto, _, sockaddr = infos[0]
    try:
        with socket.socket(family, socktype, proto) as s:
            s.settimeout(3.0)
            s.connect(sockaddr)
        return f"TCP connect to {host}:{port} OK"
    except OSError as exc:
        return f"TCP connect to {host}:{port} failed: {exc}"


def _integrity_section() -> list[str]:
    """Cross-check the DB against files on disk for each library."""
    lines: list[str] = []
    db_path = settings.db_path
    if not db_path.is_file():
        return ["- (no database)"]

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        try:
            libs = {l["id"]: Path(l["path"]) for l in conn.execute("SELECT id, path FROM libraries").fetchall()}
        except sqlite3.Error:
            return ["- (libraries table unavailable)"]

        referenced: set[Path] = set()
        missing_preview = 0
        missing_files = 0
        unresolved_lib = 0
        items = conn.execute("SELECT id, preview_path, other_files, library_id FROM items").fetchall()
        for it in items:
            root = libs.get(it["library_id"])
            if root is None:
                unresolved_lib += 1
                continue
            if it["preview_path"]:
                p = root / it["preview_path"]
                referenced.add(p.resolve())
                if not p.is_file():
                    missing_preview += 1
            try:
                others = json.loads(it["other_files"]) if it["other_files"] else []
            except (json.JSONDecodeError, TypeError):
                others = []
            for f in others:
                p = root / f
                referenced.add(p.resolve())
                if not p.is_file():
                    missing_files += 1

        # Orphans: files on disk under each library root not referenced by any item.
        orphans = 0
        for root in set(libs.values()):
            if not root.is_dir():
                continue
            for p in root.rglob("*"):
                if p.is_file() and p.resolve() not in referenced:
                    orphans += 1

        lines.append(f"- Items checked: {len(items)}")
        lines.append(f"- Items with missing preview file: {missing_preview}")
        lines.append(f"- Item files missing on disk: {missing_files}")
        lines.append(f"- Items with unresolved library: {unresolved_lib}")
        lines.append(f"- Orphaned files on disk (no DB reference): {orphans}")
    finally:
        conn.close()
    return lines


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
    if os.environ.get("CC_SECRET_KEY_FILE"):
        secret_source = "CC_SECRET_KEY_FILE"
    elif os.environ.get("CC_SECRET_KEY"):
        secret_source = "CC_SECRET_KEY"
    else:
        secret_source = "auto-generated (persisted under data dir)"

    out: list[str] = []
    out.append("# CatalogueCanvas Diagnostic Report")
    out.append("")
    out.append(f"Generated: {datetime.now(timezone.utc).isoformat()}")
    out.append("")

    out.append("## Versions")
    out.append(f"- App version: {_app_version()}")
    out.append(f"- Git SHA: {_git_sha()}")
    out.append(f"- Build date: {settings.build_date}")
    out.append(f"- Python: {platform.python_version()} ({sys.implementation.name})")
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
    out.append(f"- Cookie secure: {settings.cookie_secure}")
    out.append(f"- Data dir: `{settings.data_dir}` (exists: {settings.data_dir.is_dir()})")
    out.append(f"- Storage dir: `{settings.storage_dir}` (exists: {settings.storage_dir.is_dir()})")
    out.append(f"- Static dir: `{settings.static_dir}` (exists: {settings.static_dir.is_dir()})")
    out.append(f"- Max upload bytes: {settings.max_upload_bytes:,}")
    out.append(f"- Max zip member bytes: {settings.max_zip_member_bytes:,}")
    out.append(f"- Max zip total bytes: {settings.max_zip_total_bytes:,}")
    out.append("")

    out.append("## Disk & storage")
    out.extend(_disk_section())
    out.append("")

    out.append("## LLM")
    out.extend(_llm_section())
    out.append("")

    out.append("## Database")
    out.extend(_db_section())
    out.append("")

    out.append("## Storage integrity")
    out.extend(_integrity_section())
    out.append("")

    return "\n".join(out)
