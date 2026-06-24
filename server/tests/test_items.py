"""Tests for routers/items.py — pure helpers plus endpoint round-trips.

Endpoint tests seed items through the ``app_conn`` fixture (the app's global DB)
and drive the real app via the ``admin`` TestClient.
"""
from __future__ import annotations

import io

from cataloguecanvas import db
from cataloguecanvas.routers import items as items_router


def csrf(client):
    token = client.cookies.get("cc_csrf")
    return {"X-CSRF-Token": token} if token else {}


def seed_item(conn, item_id="apple-001", **over):
    rec = {
        "id": item_id,
        "content_hash": f"hash-{item_id}",
        "title": "My Item",
        "note": "a note",
        "mime_type": "image/webp",
        "preview_path": f"{item_id}/preview.webp",
        "other_files": [],
        "tags": ["red"],
        "raw_meta": {},
        "library_id": db.get_default_library(conn)["id"],
    }
    rec.update(over)
    db.upsert_item(conn, rec)
    return rec


# --- pure helpers ---

def test_file_type():
    assert items_router._file_type("a.png") == "image"
    assert items_router._file_type("a.MD") == "text"
    assert items_router._file_type("a.bin") == "other"
    assert items_router._file_type("a.txt.lz4") == "other"  # compressed = download-only


def test_json_field():
    assert items_router._json_field('["a","b"]') == ["a", "b"]
    assert items_router._json_field("not json") == "not json"
    assert items_router._json_field(None) == []
    assert items_router._json_field(["x"]) == ["x"]


def test_enrich_builds_urls_and_title():
    enriched = items_router._enrich({
        "id": "foo-bar", "library_id": "lib1", "preview_path": "foo/p.webp",
        "tags": '["t"]', "raw_meta": "{}", "other_files": '["foo/doc.txt"]', "title": "",
    })
    assert enriched["preview_url"] == "/storage/lib1/foo/p.webp"
    assert enriched["tags"] == ["t"]
    assert enriched["title"] == "Foo Bar"  # derived from id when blank
    assert enriched["download_urls"][0]["type"] == "text"


def test_enrich_public_preview_route():
    enriched = items_router._enrich(
        {"id": "x", "library_id": "lib1", "preview_path": "x/p.webp"}, public=True)
    assert enriched["preview_url"].startswith("/p-storage/")


def test_tags_cell_roundtrip():
    assert items_router._tags_to_cell('["a","b"]') == "a; b"
    assert items_router._cell_to_tags("a; b, c") == ["a", "b", "c"]
    assert items_router._cell_to_tags("") == []


# --- endpoints ---

def test_list_and_get_item(admin, app_conn):
    seed_item(app_conn)
    listed = admin.get("/api/items").json()
    assert any(i["id"] == "apple-001" for i in listed)
    one = admin.get("/api/items/apple-001")
    assert one.status_code == 200
    assert one.json()["title"] == "My Item"


def test_patch_item(admin, app_conn):
    seed_item(app_conn, "pear-002", content_hash="h2")
    resp = admin.patch("/api/items/pear-002", json={"title": "Renamed"}, headers=csrf(admin))
    assert resp.status_code == 200
    assert resp.json()["title"] == "Renamed"


def test_favorite_and_unfavorite(admin, app_conn):
    seed_item(app_conn, "fig-003", content_hash="h3")
    fav = admin.post("/api/items/fig-003/favorite", headers=csrf(admin))
    assert fav.status_code == 200
    assert "favorites" in fav.json()["collection_ids"]
    unfav = admin.request("DELETE", "/api/items/fig-003/favorite", headers=csrf(admin))
    assert "favorites" not in unfav.json()["collection_ids"]


def test_delete_item(admin, app_conn):
    seed_item(app_conn, "gone-004", content_hash="h4")
    resp = admin.request("DELETE", "/api/items/gone-004", headers=csrf(admin))
    assert resp.status_code == 200
    assert admin.get("/api/items/gone-004").status_code == 404


def test_search_endpoint(admin, app_conn):
    seed_item(app_conn, "sun-005", content_hash="h5", title="Sunset glow")
    hits = admin.get("/api/items/search?q=sunset").json()
    assert any(h["id"] == "sun-005" for h in hits)


# --- bulk actions ---

def test_bulk_tags_and_clear_notes(admin, app_conn):
    seed_item(app_conn, "b-1", content_hash="hb1", tags=["x"])
    tagged = admin.post("/api/items/bulk/tags",
                        json={"item_ids": ["b-1", "missing"], "tags": ["y"]},
                        headers=csrf(admin)).json()
    assert tagged["updated"] == ["b-1"]
    assert tagged["missing"] == ["missing"]

    cleared = admin.post("/api/items/bulk/clear-notes",
                         json={"item_ids": ["b-1"]}, headers=csrf(admin)).json()
    assert cleared["updated"] == ["b-1"]


def test_bulk_favorite_unfavorite(admin, app_conn):
    seed_item(app_conn, "b-2", content_hash="hb2")
    fav = admin.post("/api/items/bulk/favorite",
                     json={"item_ids": ["b-2"]}, headers=csrf(admin)).json()
    assert fav["updated"] == ["b-2"]
    unfav = admin.post("/api/items/bulk/unfavorite",
                       json={"item_ids": ["b-2"]}, headers=csrf(admin)).json()
    assert unfav["updated"] == ["b-2"]


# --- CSV round-trip ---

def test_csv_export_then_preview_and_import(admin, app_conn):
    seed_item(app_conn, "csv-1", content_hash="hc1", title="Old", note="n", tags=["a"])

    # export
    exported = admin.post("/api/items/export/csv", json={"q": ""}, headers=csrf(admin))
    assert exported.status_code == 200
    assert "csv-1" in exported.text

    # build a CSV that changes the title
    csv_body = "id,title,note,tags\ncsv-1,New Title,n,a\n"
    upload = ("edit.csv", io.BytesIO(csv_body.encode()), "text/csv")

    preview = admin.post("/api/items/import/csv/preview",
                         files={"file": upload}, headers=csrf(admin)).json()
    assert preview["to_update"][0]["id"] == "csv-1"
    assert preview["to_update"][0]["title"]["new"] == "New Title"

    upload2 = ("edit.csv", io.BytesIO(csv_body.encode()), "text/csv")
    applied = admin.post("/api/items/import/csv",
                         files={"file": upload2}, headers=csrf(admin)).json()
    assert applied["updated"] == ["csv-1"]
    assert applied["backup"]  # a backup filename was written
    assert admin.get("/api/items/csv-1").json()["title"] == "New Title"


def test_csv_import_rejects_non_csv(admin):
    upload = ("x.txt", io.BytesIO(b"nope"), "text/plain")
    resp = admin.post("/api/items/import/csv/preview",
                      files={"file": upload}, headers=csrf(admin))
    assert resp.status_code == 400


def test_item_metadata_jsonld(admin, app_conn):
    seed_item(app_conn, "meta-1", content_hash="hm1", title="Titled")
    doc = admin.get("/api/items/meta-1/metadata").json()
    assert doc["@context"] == "https://schema.org"
    assert doc["identifier"] == "meta-1"
