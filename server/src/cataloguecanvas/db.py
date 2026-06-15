from __future__ import annotations
import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any, Optional

from .settings import settings

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS items (
    id            TEXT PRIMARY KEY,
    content_hash  TEXT NOT NULL UNIQUE,
    title         TEXT,
    note          TEXT,
    mime_type     TEXT,
    preview_path  TEXT,
    other_files   TEXT,
    tags          TEXT,
    collection_id TEXT,
    raw_meta      TEXT,
    ingested_at   TEXT DEFAULT (datetime('now')),
    imported_at   TEXT
);

CREATE TABLE IF NOT EXISTS collections (
    id            TEXT PRIMARY KEY,
    title         TEXT,
    description   TEXT,
    cover_item_id TEXT,
    is_system     INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS item_collections (
    item_id       TEXT NOT NULL,
    collection_id TEXT NOT NULL,
    added_at      TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (item_id, collection_id),
    FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE,
    FOREIGN KEY (collection_id) REFERENCES collections(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_item_collections_collection ON item_collections(collection_id);

CREATE TABLE IF NOT EXISTS portfolios (
    id          TEXT PRIMARY KEY,
    slug        TEXT NOT NULL UNIQUE,
    title       TEXT,
    description TEXT,
    item_ids    TEXT,
    is_public   INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS admin (
    id            INTEGER PRIMARY KEY CHECK (id = 1),
    password_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS app_settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS libraries (
    id         TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    path       TEXT NOT NULL UNIQUE,
    is_default INTEGER NOT NULL DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);
"""


def get_connection(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL)
    existing_cols = {row["name"] for row in conn.execute("PRAGMA table_info(items)")}
    for col in ("width", "height"):
        if col not in existing_cols:
            conn.execute(f"ALTER TABLE items ADD COLUMN {col} INTEGER")

    collection_cols = {row["name"] for row in conn.execute("PRAGMA table_info(collections)")}
    if "is_system" not in collection_cols:
        conn.execute("ALTER TABLE collections ADD COLUMN is_system INTEGER NOT NULL DEFAULT 0")

    conn.execute("""
        INSERT OR IGNORE INTO item_collections (item_id, collection_id)
        SELECT id, collection_id FROM items WHERE collection_id IS NOT NULL
    """)
    conn.execute("""
        INSERT OR IGNORE INTO collections (id, title, description, is_system)
        VALUES ('favorites', 'Favorites', '', 1)
    """)

    if "library_id" not in existing_cols:
        conn.execute("ALTER TABLE items ADD COLUMN library_id TEXT REFERENCES libraries(id)")

    lib_count = conn.execute("SELECT COUNT(*) FROM libraries").fetchone()[0]
    if lib_count == 0:
        default_id = f"lib-{uuid.uuid4().hex[:12]}"
        conn.execute(
            "INSERT INTO libraries (id, name, path, is_default) VALUES (?, ?, ?, 1)",
            (default_id, "Default", str(settings.storage_dir)),
        )
        conn.execute(
            "UPDATE items SET library_id = ? WHERE library_id IS NULL",
            (default_id,),
        )

    conn.commit()


def _dump(v: Any) -> Any:
    if isinstance(v, (dict, list)):
        return json.dumps(v)
    return v


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


# --- items ---

def hash_exists(conn: sqlite3.Connection, content_hash: str) -> Optional[str]:
    row = conn.execute("SELECT id FROM items WHERE content_hash = ?", (content_hash,)).fetchone()
    return row["id"] if row else None


def id_exists(conn: sqlite3.Connection, item_id: str) -> bool:
    row = conn.execute("SELECT 1 FROM items WHERE id = ?", (item_id,)).fetchone()
    return row is not None


def upsert_item(conn: sqlite3.Connection, record: dict[str, Any]) -> None:
    cols = list(record.keys())
    placeholders = ", ".join(["?" for _ in cols])
    col_names = ", ".join(cols)
    updates = ", ".join(f"{c} = excluded.{c}" for c in cols if c != "id")
    sql = f"""
        INSERT INTO items ({col_names}) VALUES ({placeholders})
        ON CONFLICT (id) DO UPDATE SET {updates}
    """
    values = [_dump(v) for v in record.values()]
    conn.execute(sql, values)
    conn.commit()


def get_item(conn: sqlite3.Connection, item_id: str) -> Optional[dict[str, Any]]:
    row = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    if not row:
        return None
    item = _row_to_dict(row)
    item["collection_ids"] = get_item_collection_ids(conn, item_id)
    return item


def get_all_items(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT * FROM items ORDER BY ingested_at DESC").fetchall()
    items = [_row_to_dict(r) for r in rows]
    membership: dict[str, list[str]] = {}
    for row in conn.execute("SELECT item_id, collection_id FROM item_collections"):
        membership.setdefault(row["item_id"], []).append(row["collection_id"])
    for item in items:
        item["collection_ids"] = membership.get(item["id"], [])
    return items


def update_item_meta(conn: sqlite3.Connection, item_id: str, fields: dict[str, Any]) -> Optional[dict[str, Any]]:
    if not fields:
        return get_item(conn, item_id)
    allowed = {"title", "note", "tags", "raw_meta"}
    fields = {k: v for k, v in fields.items() if k in allowed}
    if not fields:
        return get_item(conn, item_id)
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = [_dump(v) for v in fields.values()]
    conn.execute(f"UPDATE items SET {set_clause} WHERE id = ?", (*values, item_id))
    conn.commit()
    return get_item(conn, item_id)


def delete_item(conn: sqlite3.Connection, item_id: str) -> None:
    conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
    conn.commit()


# --- item collections (junction) ---

def get_item_collection_ids(conn: sqlite3.Connection, item_id: str) -> list[str]:
    rows = conn.execute("SELECT collection_id FROM item_collections WHERE item_id = ?", (item_id,)).fetchall()
    return [r["collection_id"] for r in rows]


def set_item_collections(conn: sqlite3.Connection, item_id: str, collection_ids: list[str]) -> None:
    conn.execute("DELETE FROM item_collections WHERE item_id = ?", (item_id,))
    conn.executemany(
        "INSERT OR IGNORE INTO item_collections (item_id, collection_id) VALUES (?, ?)",
        [(item_id, cid) for cid in collection_ids],
    )
    conn.commit()


def add_item_to_collection(conn: sqlite3.Connection, item_id: str, collection_id: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO item_collections (item_id, collection_id) VALUES (?, ?)",
        (item_id, collection_id),
    )
    conn.commit()


def remove_item_from_collection(conn: sqlite3.Connection, item_id: str, collection_id: str) -> None:
    conn.execute(
        "DELETE FROM item_collections WHERE item_id = ? AND collection_id = ?",
        (item_id, collection_id),
    )
    conn.commit()


def get_collection_items(conn: sqlite3.Connection, col_id: str) -> list[dict[str, Any]]:
    rows = conn.execute("""
        SELECT i.* FROM items i
        JOIN item_collections ic ON ic.item_id = i.id
        WHERE ic.collection_id = ?
        ORDER BY i.ingested_at DESC
    """, (col_id,)).fetchall()
    items = [_row_to_dict(r) for r in rows]
    for item in items:
        item["collection_ids"] = get_item_collection_ids(conn, item["id"])
    return items


# --- collections ---

def upsert_collection(conn: sqlite3.Connection, col: dict[str, Any]) -> None:
    conn.execute("""
        INSERT INTO collections (id, title, description, cover_item_id, is_system)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT (id) DO UPDATE SET
            title = excluded.title,
            description = excluded.description,
            cover_item_id = excluded.cover_item_id
    """, (col["id"], col.get("title", ""), col.get("description", ""), col.get("cover_item_id"), col.get("is_system", 0)))
    conn.commit()


def get_all_collections(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT * FROM collections ORDER BY created_at").fetchall()
    return [_row_to_dict(r) for r in rows]


def get_collection(conn: sqlite3.Connection, col_id: str) -> Optional[dict[str, Any]]:
    row = conn.execute("SELECT * FROM collections WHERE id = ?", (col_id,)).fetchone()
    return _row_to_dict(row) if row else None


def delete_collection(conn: sqlite3.Connection, col_id: str) -> None:
    conn.execute("DELETE FROM collections WHERE id = ?", (col_id,))
    conn.commit()


# --- portfolios ---

def upsert_portfolio(conn: sqlite3.Connection, p: dict[str, Any]) -> dict[str, Any]:
    cols = list(p.keys())
    placeholders = ", ".join(["?" for _ in cols])
    col_names = ", ".join(cols)
    updates = ", ".join(f"{c} = excluded.{c}" for c in cols if c != "id")
    sql = f"""
        INSERT INTO portfolios ({col_names}) VALUES ({placeholders})
        ON CONFLICT (id) DO UPDATE SET {updates}
    """
    values = [_dump(v) for v in p.values()]
    conn.execute(sql, values)
    conn.commit()
    return get_portfolio(conn, p["id"])


def get_portfolio(conn: sqlite3.Connection, p_id: str) -> Optional[dict[str, Any]]:
    row = conn.execute("SELECT * FROM portfolios WHERE id = ?", (p_id,)).fetchone()
    return _row_to_dict(row) if row else None


def get_portfolio_by_slug(conn: sqlite3.Connection, slug: str) -> Optional[dict[str, Any]]:
    row = conn.execute("SELECT * FROM portfolios WHERE slug = ?", (slug,)).fetchone()
    return _row_to_dict(row) if row else None


def get_all_portfolios(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT * FROM portfolios ORDER BY created_at DESC").fetchall()
    return [_row_to_dict(r) for r in rows]


def delete_portfolio(conn: sqlite3.Connection, p_id: str) -> None:
    conn.execute("DELETE FROM portfolios WHERE id = ?", (p_id,))
    conn.commit()


# --- admin ---

def get_admin_hash(conn: sqlite3.Connection) -> Optional[str]:
    row = conn.execute("SELECT password_hash FROM admin WHERE id = 1").fetchone()
    return row["password_hash"] if row else None


def set_admin_hash(conn: sqlite3.Connection, password_hash: str) -> None:
    conn.execute("""
        INSERT INTO admin (id, password_hash) VALUES (1, ?)
        ON CONFLICT (id) DO UPDATE SET password_hash = excluded.password_hash
    """, (password_hash,))
    conn.commit()


# --- app settings ---

def get_settings(conn: sqlite3.Connection) -> dict[str, str]:
    rows = conn.execute("SELECT key, value FROM app_settings").fetchall()
    return {r["key"]: r["value"] for r in rows}


def set_settings(conn: sqlite3.Connection, values: dict[str, str]) -> None:
    conn.executemany(
        """
        INSERT INTO app_settings (key, value) VALUES (?, ?)
        ON CONFLICT (key) DO UPDATE SET value = excluded.value
        """,
        list(values.items()),
    )
    conn.commit()


def get_db_stats(conn: sqlite3.Connection) -> dict[str, Any]:
    total = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    cols = conn.execute("SELECT COUNT(*) FROM collections").fetchone()[0]
    missing_preview = conn.execute("SELECT COUNT(*) FROM items WHERE preview_path IS NULL").fetchone()[0]
    return {"total_items": total, "total_collections": cols, "missing_preview": missing_preview}


# --- libraries ---

def create_library(conn: sqlite3.Connection, name: str, path: str, is_default: bool = False) -> dict[str, Any]:
    lib_id = f"lib-{uuid.uuid4().hex[:12]}"
    if is_default:
        conn.execute("UPDATE libraries SET is_default = 0")
    conn.execute(
        "INSERT INTO libraries (id, name, path, is_default) VALUES (?, ?, ?, ?)",
        (lib_id, name, path, 1 if is_default else 0),
    )
    conn.commit()
    return get_library(conn, lib_id)


def get_library(conn: sqlite3.Connection, lib_id: str) -> Optional[dict[str, Any]]:
    row = conn.execute("SELECT * FROM libraries WHERE id = ?", (lib_id,)).fetchone()
    return _row_to_dict(row) if row else None


def get_all_libraries(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT * FROM libraries ORDER BY created_at").fetchall()
    return [_row_to_dict(r) for r in rows]


def get_default_library(conn: sqlite3.Connection) -> Optional[dict[str, Any]]:
    row = conn.execute("SELECT * FROM libraries WHERE is_default = 1").fetchone()
    return _row_to_dict(row) if row else None


def update_library(conn: sqlite3.Connection, lib_id: str, fields: dict[str, Any]) -> Optional[dict[str, Any]]:
    allowed = {"name", "path"}
    fields = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if fields:
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        conn.execute(f"UPDATE libraries SET {set_clause} WHERE id = ?", (*fields.values(), lib_id))
        conn.commit()
    return get_library(conn, lib_id)


def set_default_library(conn: sqlite3.Connection, lib_id: str) -> Optional[dict[str, Any]]:
    conn.execute("UPDATE libraries SET is_default = 0")
    conn.execute("UPDATE libraries SET is_default = 1 WHERE id = ?", (lib_id,))
    conn.commit()
    return get_library(conn, lib_id)


def library_item_count(conn: sqlite3.Connection, lib_id: str) -> int:
    return conn.execute("SELECT COUNT(*) FROM items WHERE library_id = ?", (lib_id,)).fetchone()[0]


def delete_library(conn: sqlite3.Connection, lib_id: str) -> None:
    conn.execute("DELETE FROM libraries WHERE id = ?", (lib_id,))
    conn.commit()
