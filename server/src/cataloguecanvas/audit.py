"""Append-only activity log.

Records who did what, when: uploads, deletions, metadata edits, collection and
portfolio changes, logins, and settings updates. One JSON object per line
(JSONL) under ``<CC_DATA_DIR>/logs/audit.log``, so the file can be tailed from
the host, shipped to a log collector, or read back for the Settings panel
without a schema migration.

Two rules hold everywhere in this module:

- **Nothing raises.** A read-only volume, a full disk, or a corrupt line must
  never turn a successful upload into a 500. Every filesystem touch is guarded
  and failures go to ``logger.debug``. Same contract as ``telemetry.capture``.
- **No secrets.** Callers pass field *names*, never values: notes, prompt
  templates and the LLM api_url all flow through the same endpoints, and a
  password reset must not leave the password on disk.
"""
from __future__ import annotations
import csv
import io
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .settings import settings

logger = logging.getLogger(__name__)

# Column order for the CSV export. `detail` is JSON-encoded into a single cell
# so the shape stays stable no matter which keys a given action carries.
CSV_COLUMNS = ["at", "actor", "role", "action", "target", "detail"]


def _log_path() -> Path:
    return settings.audit_log_path


def _rotated_path() -> Path:
    path = _log_path()
    return path.with_name(path.name + ".1")


def _rotate_if_needed(path: Path) -> None:
    """Roll the log over once it passes the size cap, keeping one old file.

    Size-based only: there is no scheduler in the app, so time-based rotation
    would need one. Called before each append, which is the only moment the
    file grows.
    """
    max_bytes = settings.audit_log_max_bytes
    if max_bytes <= 0:
        return
    try:
        if path.stat().st_size < max_bytes:
            return
    except OSError:
        # No file yet, or it can't be stat'd. Either way there is nothing to
        # rotate; the append below will surface a real problem if one exists.
        return
    try:
        os.replace(path, _rotated_path())
    except OSError:
        logger.debug("could not rotate audit log at %s", path, exc_info=True)


def log_event(
    action: str,
    actor: Optional[str] = None,
    role: Optional[str] = None,
    target: Optional[str] = None,
    **detail: Any,
) -> None:
    """Append one event. No-op when logging is disabled. Never raises."""
    if not settings.audit_log_enabled:
        return

    entry = {
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "actor": actor,
        "role": role,
        "action": action,
        "target": target,
        "detail": detail,
    }

    path = _log_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        _rotate_if_needed(path)
        # Single append-mode write of one line: the O_APPEND write is atomic for
        # payloads this small, so concurrent workers interleave whole lines
        # rather than corrupting each other's.
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
    except (OSError, TypeError, ValueError):
        logger.debug("could not write audit event %s", action, exc_info=True)


def _read_file(path: Path) -> list[dict]:
    entries: list[dict] = []
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    parsed = json.loads(line)
                except json.JSONDecodeError:
                    # A truncated final line (crash mid-write) shouldn't hide
                    # every other entry.
                    continue
                if isinstance(parsed, dict):
                    entries.append(parsed)
    except OSError:
        logger.debug("could not read audit log at %s", path, exc_info=True)
    return entries


def read_events(limit: Optional[int] = None) -> list[dict]:
    """Return events newest-first, spanning the rotated file when present."""
    entries = _read_file(_rotated_path()) + _read_file(_log_path())
    entries.reverse()
    if limit is not None and limit >= 0:
        return entries[:limit]
    return entries


def export_csv() -> str:
    """Render the whole log as CSV, newest first."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(CSV_COLUMNS)
    for entry in read_events():
        detail = entry.get("detail")
        writer.writerow([
            entry.get("at") or "",
            entry.get("actor") or "",
            entry.get("role") or "",
            entry.get("action") or "",
            entry.get("target") or "",
            json.dumps(detail, ensure_ascii=False, default=str) if detail else "",
        ])
    return buffer.getvalue()


def clear() -> None:
    """Delete the log and its rotated companion. Never raises."""
    for path in (_log_path(), _rotated_path()):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            logger.debug("could not delete audit log at %s", path, exc_info=True)
