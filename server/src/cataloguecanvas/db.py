from __future__ import annotations
import json
import sqlite3
from pathlib import Path
from typing import Any, Optional

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
    created_at    TEXT DEFAULT (datetime('now'))
);

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
    return _row_to_dict(row) if row else None


def get_all_items(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT * FROM items ORDER BY ingested_at DESC").fetchall()
    return [_row_to_dict(r) for r in rows]


def update_item_meta(conn: sqlite3.Connection, item_id: str, fields: dict[str, Any]) -> Optional[dict[str, Any]]:
    if not fields:
        return get_item(conn, item_id)
    allowed = {"title", "note", "tags", "collection_id", "raw_meta"}
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


# --- collections ---

def upsert_collection(conn: sqlite3.Connection, col: dict[str, Any]) -> None:
    conn.execute("""
        INSERT INTO collections (id, title, description, cover_item_id)
        VALUES (?, ?, ?, ?)
        ON CONFLICT (id) DO UPDATE SET
            title = excluded.title,
            description = excluded.description,
            cover_item_id = excluded.cover_item_id
    """, (col["id"], col.get("title", ""), col.get("description", ""), col.get("cover_item_id")))
    conn.commit()


def get_all_collections(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT * FROM collections ORDER BY created_at").fetchall()
    return [_row_to_dict(r) for r in rows]


def get_collection(conn: sqlite3.Connection, col_id: str) -> Optional[dict[str, Any]]:
    row = conn.execute("SELECT * FROM collections WHERE id = ?", (col_id,)).fetchone()
    return _row_to_dict(row) if row else None


def delete_collection(conn: sqlite3.Connection, col_id: str) -> None:
    conn.execute("UPDATE items SET collection_id = NULL WHERE collection_id = ?", (col_id,))
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
