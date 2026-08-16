from __future__ import annotations
import json

import pytest

from cataloguecanvas import audit
from cataloguecanvas.settings import settings


@pytest.fixture()
def log_path(tmp_path, monkeypatch):
    """Point the audit log at a per-test file and force logging on."""
    path = tmp_path / "logs" / "audit.log"
    monkeypatch.setattr(settings, "audit_log_path", path)
    monkeypatch.setattr(settings, "audit_log_enabled", True)
    monkeypatch.setattr(settings, "audit_log_max_bytes", 5 * 1024 * 1024)
    return path


def test_log_event_writes_jsonl(log_path):
    audit.log_event("item.upload", actor="admin", role="admin", target="summary-916", created=True)

    lines = log_path.read_text().strip().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["action"] == "item.upload"
    assert entry["actor"] == "admin"
    assert entry["target"] == "summary-916"
    assert entry["detail"] == {"created": True}
    assert entry["at"].endswith("+00:00")


def test_log_event_creates_parent_directory(log_path):
    assert not log_path.parent.exists()
    audit.log_event("test.event")
    assert log_path.is_file()


def test_log_event_is_noop_when_disabled(log_path, monkeypatch):
    monkeypatch.setattr(settings, "audit_log_enabled", False)
    audit.log_event("item.delete", actor="admin")
    assert not log_path.exists()


def test_log_event_never_raises_on_unwritable_path(tmp_path, monkeypatch):
    # Parent exists as a *file*, so mkdir and open both fail. A broken log must
    # not propagate into the request that triggered it.
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory")
    monkeypatch.setattr(settings, "audit_log_path", blocker / "audit.log")
    monkeypatch.setattr(settings, "audit_log_enabled", True)

    audit.log_event("item.upload", actor="admin")  # must not raise


def test_read_events_returns_newest_first(log_path):
    audit.log_event("first")
    audit.log_event("second")
    audit.log_event("third")

    events = audit.read_events()
    assert [e["action"] for e in events] == ["third", "second", "first"]


def test_read_events_honors_limit(log_path):
    for i in range(5):
        audit.log_event(f"event.{i}")
    assert len(audit.read_events(limit=2)) == 2


def test_read_events_skips_corrupt_lines(log_path):
    audit.log_event("good.one")
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write("{not valid json\n")
    audit.log_event("good.two")

    actions = [e["action"] for e in audit.read_events()]
    assert actions == ["good.two", "good.one"]


def test_read_events_on_missing_file(log_path):
    assert audit.read_events() == []


def test_rotation_keeps_recent_entries(log_path, monkeypatch):
    """Rotation keeps one previous file, so the newest entries always survive.

    Only two generations are retained by design -- anything older is dropped
    rather than growing the data dir without bound. Operators who need full
    history export the CSV or ship the file elsewhere.
    """
    monkeypatch.setattr(settings, "audit_log_max_bytes", 200)
    for i in range(20):
        audit.log_event(f"event.{i}", target="x" * 20)

    rotated = log_path.with_name(log_path.name + ".1")
    assert rotated.is_file(), "expected the log to roll over"

    actions = [e["action"] for e in audit.read_events()]
    assert actions[0] == "event.19", "newest entry must be first and present"
    # Spans both files, so more than just the current one is readable.
    assert len(actions) > 1


def test_export_csv_has_header_and_rows(log_path):
    audit.log_event("item.delete", actor="admin", role="admin", target="abc-123", title="Old")

    csv_text = audit.export_csv()
    lines = csv_text.strip().splitlines()
    assert lines[0] == "at,actor,role,action,target,detail"
    assert "item.delete" in lines[1]
    assert "abc-123" in lines[1]


def test_clear_removes_log_and_rotated_file(log_path, monkeypatch):
    monkeypatch.setattr(settings, "audit_log_max_bytes", 200)
    for i in range(20):
        audit.log_event(f"event.{i}", target="x" * 20)
    rotated = log_path.with_name(log_path.name + ".1")
    assert rotated.is_file()

    audit.clear()

    assert not log_path.exists()
    assert not rotated.exists()
    assert audit.read_events() == []


def test_clear_on_missing_file_does_not_raise(log_path):
    audit.clear()


def test_detail_with_unserializable_value_still_logs(log_path):
    # `default=str` keeps an odd value from dropping the whole entry.
    audit.log_event("test.event", value=object())
    entries = audit.read_events()
    assert len(entries) == 1
    assert "object object" in entries[0]["detail"]["value"]
