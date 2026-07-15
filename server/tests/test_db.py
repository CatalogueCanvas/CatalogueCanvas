from __future__ import annotations

import time

import pytest

from cataloguecanvas import db


def _item(item_id="apple-001", **over):
    rec = {
        "id": item_id,
        "content_hash": f"hash-{item_id}",
        "title": "A Title",
        "note": "a note",
        "mime_type": "image/webp",
        "preview_path": f"{item_id}/preview.webp",
        "other_files": [],
        "tags": ["red", "fruit"],
        "raw_meta": {"camera": "leica", "iso": 100},
    }
    rec.update(over)
    return rec


# --- items ---

def test_upsert_and_get_item(conn):
    db.upsert_item(conn, _item())
    got = db.get_item(conn, "apple-001")
    assert got["title"] == "A Title"
    assert got["collection_ids"] == []
    assert db.id_exists(conn, "apple-001") is True
    assert db.hash_exists(conn, "hash-apple-001") == "apple-001"


def test_upsert_item_rejects_unknown_column(conn):
    with pytest.raises(ValueError, match="unknown column"):
        db.upsert_item(conn, _item(**{"id; DROP TABLE items": "x"}))


def test_get_item_missing(conn):
    assert db.get_item(conn, "nope") is None
    assert db.id_exists(conn, "nope") is False
    assert db.hash_exists(conn, "nope") is None


def test_get_all_items_order_and_membership(conn):
    db.upsert_item(conn, _item("a-001"))
    db.upsert_item(conn, _item("b-002", content_hash="h2"))
    items = db.get_all_items(conn)
    assert {i["id"] for i in items} == {"a-001", "b-002"}


def test_update_item_meta(conn):
    db.upsert_item(conn, _item())
    updated = db.update_item_meta(conn, "apple-001", {"title": "New", "ignored": "x"})
    assert updated["title"] == "New"
    # empty fields returns current item
    assert db.update_item_meta(conn, "apple-001", {})["title"] == "New"
    # only-disallowed fields returns current item
    assert db.update_item_meta(conn, "apple-001", {"ignored": "x"})["title"] == "New"


def test_delete_item(conn):
    db.upsert_item(conn, _item())
    db.delete_item(conn, "apple-001")
    assert db.get_item(conn, "apple-001") is None


# --- search ---

def test_search_items_matches_and_empty(conn):
    db.upsert_item(conn, _item(title="Sunset over water"))
    db.upsert_item(conn, _item("pear-002", content_hash="h2", title="Mountain"))
    hits = db.search_items(conn, "sunset")
    assert [h["id"] for h in hits] == ["apple-001"]
    # empty query returns everything
    assert len(db.search_items(conn, "   ")) == 2


def test_flatten_meta():
    out = db.flatten_meta({"a": 1, "b": [{"c": "x"}, "y"], "d": None})
    assert "a" in out and "1" in out and "c" in out and "x" in out and "y" in out


# --- collections + junction ---

def test_collections_crud(conn):
    db.upsert_collection(conn, {"id": "col1", "title": "Col", "description": "d"})
    assert db.get_collection(conn, "col1")["title"] == "Col"
    assert any(c["id"] == "col1" for c in db.get_all_collections(conn))
    db.upsert_collection(conn, {"id": "col1", "title": "Col2"})
    assert db.get_collection(conn, "col1")["title"] == "Col2"
    db.delete_collection(conn, "col1")
    assert db.get_collection(conn, "col1") is None


def test_item_collection_membership(conn):
    db.upsert_item(conn, _item())
    db.upsert_collection(conn, {"id": "col1", "title": "C"})
    db.add_item_to_collection(conn, "apple-001", "col1")
    assert db.get_item_collection_ids(conn, "apple-001") == ["col1"]
    assert [i["id"] for i in db.get_collection_items(conn, "col1")] == ["apple-001"]
    db.remove_item_from_collection(conn, "apple-001", "col1")
    assert db.get_item_collection_ids(conn, "apple-001") == []
    db.set_item_collections(conn, "apple-001", ["col1", "favorites"])
    assert set(db.get_item_collection_ids(conn, "apple-001")) == {"col1", "favorites"}


# --- portfolios ---

def test_portfolio_crud_and_public_ids(conn):
    p = db.upsert_portfolio(conn, {
        "id": "p1", "slug": "my-slug", "title": "P", "description": "",
        "item_ids": ["apple-001"], "is_public": 1, "style": "ledger",
    })
    assert p["slug"] == "my-slug"
    assert db.get_portfolio(conn, "p1")["title"] == "P"
    assert db.get_portfolio_by_slug(conn, "my-slug")["id"] == "p1"
    assert any(pp["id"] == "p1" for pp in db.get_all_portfolios(conn))
    assert db.get_public_item_ids(conn) == {"apple-001"}
    db.delete_portfolio(conn, "p1")
    assert db.get_portfolio(conn, "p1") is None


def test_portfolio_layout_defaults_to_slide(conn):
    db.upsert_portfolio(conn, {
        "id": "p1", "slug": "my-slug", "title": "P", "description": "",
        "item_ids": [], "is_public": 0, "style": "ledger",
    })
    assert db.get_portfolio(conn, "p1")["layout"] == "slide"


def test_portfolio_style_and_layout_are_independent(conn):
    db.upsert_portfolio(conn, {
        "id": "p1", "slug": "s1", "title": "P", "description": "",
        "item_ids": [], "is_public": 0, "style": "riso", "layout": "scroll",
    })
    got = db.get_portfolio(conn, "p1")
    assert (got["style"], got["layout"]) == ("riso", "scroll")

    # Changing the layout leaves the style alone, and vice versa.
    db.upsert_portfolio(conn, {"id": "p1", "slug": "s1", "layout": "slide"})
    got = db.get_portfolio(conn, "p1")
    assert (got["style"], got["layout"]) == ("riso", "slide")

    db.upsert_portfolio(conn, {"id": "p1", "slug": "s1", "style": "kinetic"})
    got = db.get_portfolio(conn, "p1")
    assert (got["style"], got["layout"]) == ("kinetic", "slide")


def test_ensure_schema_adds_layout_to_preexisting_portfolios(conn):
    """A database created before layout modes existed gains the column, and its
    portfolios keep the slide deck they were published as."""
    conn.execute("DROP TABLE portfolios")
    conn.execute("""
        CREATE TABLE portfolios (
            id TEXT PRIMARY KEY, slug TEXT NOT NULL UNIQUE, title TEXT,
            description TEXT, item_ids TEXT, is_public INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.execute("INSERT INTO portfolios (id, slug, title) VALUES ('old', 'old-slug', 'Old')")

    db.ensure_schema(conn)
    assert db.get_portfolio(conn, "old")["layout"] == "slide"

    # Idempotent: a second run over the migrated DB is a no-op.
    db.ensure_schema(conn)
    assert db.get_portfolio(conn, "old")["layout"] == "slide"


def test_is_public_storage_path(conn):
    lib_id = db.get_default_library(conn)["id"]
    db.upsert_item(conn, _item(preview_path="apple-001/preview.webp", library_id=lib_id))
    db.upsert_portfolio(conn, {
        "id": "p1", "slug": "s", "title": "P", "description": "",
        "item_ids": ["apple-001"], "is_public": 1,
    })
    assert db.is_public_storage_path(conn, lib_id, "apple-001/preview.webp") is True
    assert db.is_public_storage_path(conn, lib_id, "other.webp") is False


def test_is_public_storage_path_no_public(conn):
    assert db.is_public_storage_path(conn, "libx", "x") is False


# --- sessions ---

def test_session_lifecycle(conn):
    db.create_session(conn, "sid1", "admin", "admin")
    assert db.session_exists(conn, "sid1") is True
    db.delete_session(conn, "sid1")
    assert db.session_exists(conn, "sid1") is False


# --- login throttle ---

def test_login_throttle(conn):
    now = time.time()
    db.record_login_failure(conn, "scope", now)
    db.record_login_failure(conn, "scope", now)
    assert db.count_recent_login_failures(conn, "scope", now - 10) == 2
    db.prune_login_failures(conn, now + 100)
    assert db.count_recent_login_failures(conn, "scope", now - 10) == 0
    db.record_login_failure(conn, "scope", now)
    db.clear_login_failures(conn, "scope")
    assert db.count_recent_login_failures(conn, "scope", now - 10) == 0


# --- admin / users ---

def test_admin_hash(conn):
    db.set_admin_hash(conn, "h1")
    assert db.get_admin_hash(conn) == "h1"
    db.set_admin_hash(conn, "h2")
    assert db.get_admin_hash(conn) == "h2"


def test_users_crud(conn):
    uid = db.create_user(conn, "alice", "h", "admin")
    assert db.get_user(conn, uid)["username"] == "alice"
    assert db.get_user_by_username(conn, "alice")["id"] == uid
    assert db.count_admins(conn) == 1
    db.update_user(conn, uid, username="alice2", role="reader")
    assert db.get_user(conn, uid)["username"] == "alice2"
    db.update_user(conn, uid)  # no-op branch
    assert [u["username"] for u in db.list_users(conn)] == ["alice2"]
    db.delete_user(conn, uid)
    assert db.get_user(conn, uid) is None


# --- settings + stats ---

def test_settings_roundtrip(conn):
    db.set_settings(conn, {"theme": "dark", "accent": "cobalt"})
    db.set_settings(conn, {"theme": "light"})
    s = db.get_settings(conn)
    assert s["theme"] == "light" and s["accent"] == "cobalt"


def test_db_stats(conn):
    db.upsert_item(conn, _item(preview_path=None))
    stats = db.get_db_stats(conn)
    assert stats["total_items"] == 1
    assert stats["missing_preview"] == 1


# --- libraries ---

def test_libraries_crud(conn):
    lib = db.create_library(conn, "Photos", "/data/photos", is_default=True)
    lid = lib["id"]
    assert db.get_library(conn, lid)["name"] == "Photos"
    assert db.get_default_library(conn)["id"] == lid
    assert any(l["id"] == lid for l in db.get_all_libraries(conn))
    db.update_library(conn, lid, {"name": "Pics", "bad": "x"})
    assert db.get_library(conn, lid)["name"] == "Pics"
    assert db.library_item_count(conn, lid) == 0
    other = db.create_library(conn, "Art", "/data/art")
    db.set_default_library(conn, other["id"])
    assert db.get_default_library(conn)["id"] == other["id"]
    db.delete_library(conn, lid)
    assert db.get_library(conn, lid) is None
