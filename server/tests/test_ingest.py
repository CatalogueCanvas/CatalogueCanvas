from __future__ import annotations

import io
import json
import zipfile

import pytest
from PIL import Image

from cataloguecanvas import db
from cataloguecanvas import ingest


# --- pure helpers ---

def test_mime_type():
    assert ingest._mime_type("a.png") == "image/png"
    assert ingest._mime_type("a.svg") == "image/svg+xml"
    assert ingest._mime_type("a.unknownext") is None


def test_unique_name(tmp_path):
    assert ingest._unique_name(tmp_path, "a.txt") == "a.txt"
    (tmp_path / "a.txt").write_text("x")
    assert ingest._unique_name(tmp_path, "a.txt") == "a_1.txt"
    (tmp_path / "a_1.txt").write_text("x")
    assert ingest._unique_name(tmp_path, "a.txt") == "a_2.txt"


def test_select_preview_priority():
    members = ["a.jpg", "b.png", "c.txt"]
    choice, candidates = ingest._select_preview(members)
    # png outranks jpeg in PREVIEW_MIME_PRIORITY
    assert choice == ("b.png", "image/png")
    assert candidates == ["b.png"]


def test_select_preview_none():
    choice, candidates = ingest._select_preview(["a.txt", "b.md"])
    assert choice is None and candidates == []


def test_read_member_capped_enforces_limit():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("big.bin", b"x" * 5000)
    buf.seek(0)
    with zipfile.ZipFile(buf) as zf:
        assert ingest._read_member_capped(zf, "big.bin", 10000) == b"x" * 5000
        with pytest.raises(ValueError, match="exceeds max size"):
            ingest._read_member_capped(zf, "big.bin", 100)


def test_write_other_file_compresses_svg(tmp_path):
    rel = ingest._write_other_file(tmp_path / "other", "icon.svg", b"<svg/>", tmp_path)
    assert rel.endswith("icon.svg.lz4")
    rel2 = ingest._write_other_file(tmp_path / "other", "doc.txt", b"hi", tmp_path)
    assert rel2.endswith("doc.txt")


# --- ingest_zip_bytes (full path with a real zip) ---

def _png_bytes(color=(200, 30, 30)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (32, 24), color).save(buf, format="PNG")
    return buf.getvalue()


def _make_zip(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return buf.getvalue()


def test_ingest_zip_creates_item(conn, tmp_path):
    lib = db.get_default_library(conn)
    zip_bytes = _make_zip({
        "art.png": _png_bytes(),
        "metadata.json": json.dumps({"artist": "x"}).encode(),
        "notes.txt": b"hello",
        "__MACOSX/junk": b"ignore",
        ".DS_Store": b"noise",
    })
    result = ingest.ingest_zip_bytes(
        zip_bytes, "MyArtwork.zip", conn, lib["id"], tmp_path, image_scale=1.0)
    assert result.created is True
    assert result.item["title"] == "MyArtwork"
    assert result.item["mime_type"] == "image/png"
    assert json.loads(result.item["raw_meta"]) == {"artist": "x"}
    # preview webp written under the library tree
    assert (tmp_path / result.item["preview_path"]).exists()


def test_ingest_zip_dedup_by_hash(conn, tmp_path):
    lib = db.get_default_library(conn)
    zip_bytes = _make_zip({"art.png": _png_bytes()})
    first = ingest.ingest_zip_bytes(zip_bytes, "a.zip", conn, lib["id"], tmp_path, image_scale=1.0)
    assert first.created is True
    again = ingest.ingest_zip_bytes(zip_bytes, "a.zip", conn, lib["id"], tmp_path, image_scale=1.0)
    assert again.created is False
    assert again.note == "already ingested"


def test_ingest_zip_rejects_too_many_entries(conn, tmp_path, monkeypatch):
    monkeypatch.setattr(ingest.settings, "max_zip_entries", 1)
    zip_bytes = _make_zip({"a.txt": b"1", "b.txt": b"2"})
    with pytest.raises(ValueError, match="more than 1 entries"):
        ingest.ingest_zip_bytes(zip_bytes, "x.zip", conn, "lib", tmp_path)
