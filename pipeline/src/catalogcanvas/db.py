from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Optional
import duckdb


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS items (
    id            VARCHAR PRIMARY KEY,
    content_hash  VARCHAR NOT NULL UNIQUE,
    title         VARCHAR,
    note          VARCHAR,
    mime_type     VARCHAR,
    zip_path      VARCHAR,
    preview_path  VARCHAR,
    other_files   JSON,
    tags          VARCHAR[],
    collection_id VARCHAR,
    raw_meta      JSON,
    ingested_at   TIMESTAMPTZ DEFAULT current_timestamp,
    imported_at   VARCHAR
);

CREATE TABLE IF NOT EXISTS collections (
    id            VARCHAR PRIMARY KEY,
    title         VARCHAR,
    description   VARCHAR,
    cover_item_id VARCHAR,
    created_at    TIMESTAMPTZ DEFAULT current_timestamp
);

CREATE TABLE IF NOT EXISTS site_config (
    key   VARCHAR PRIMARY KEY,
    value JSON
);
"""


def get_connection(db_path: Path) -> duckdb.DuckDBPyConnection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(db_path))


def ensure_schema(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(SCHEMA_SQL)


def hash_exists(conn: duckdb.DuckDBPyConnection, content_hash: str) -> Optional[str]:
    """Return existing item id if hash already in DB, else None."""
    row = conn.execute(
        "SELECT id FROM items WHERE content_hash = ?", [content_hash]
    ).fetchone()
    return row[0] if row else None


def id_exists(conn: duckdb.DuckDBPyConnection, item_id: str) -> bool:
    row = conn.execute("SELECT 1 FROM items WHERE id = ?", [item_id]).fetchone()
    return row is not None


def upsert_item(conn: duckdb.DuckDBPyConnection, record: dict[str, Any]) -> None:
    cols = list(record.keys())
    placeholders = ", ".join(["?" for _ in cols])
    col_names = ", ".join(cols)
    updates = ", ".join(f"{c} = excluded.{c}" for c in cols if c != "id")
    sql = f"""
        INSERT INTO items ({col_names}) VALUES ({placeholders})
        ON CONFLICT (id) DO UPDATE SET {updates}
    """
    values = [
        json.dumps(v) if isinstance(v, (dict, list)) else v
        for v in record.values()
    ]
    conn.execute(sql, values)


def upsert_collection(conn: duckdb.DuckDBPyConnection, col: dict[str, Any]) -> None:
    conn.execute("""
        INSERT INTO collections (id, title, description, cover_item_id)
        VALUES (?, ?, ?, ?)
        ON CONFLICT (id) DO UPDATE SET
            title = excluded.title,
            description = excluded.description,
            cover_item_id = excluded.cover_item_id
    """, [col["id"], col["title"], col.get("description", ""), col.get("cover_item_id", "")])


def _rows_to_dicts(rel) -> list[dict[str, Any]]:
    cols = [d[0] for d in rel.description]
    return [dict(zip(cols, row)) for row in rel.fetchall()]


def get_all_items(conn: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    return _rows_to_dicts(conn.execute("SELECT * FROM items ORDER BY ingested_at DESC"))


def get_all_collections(conn: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    return _rows_to_dicts(conn.execute("SELECT * FROM collections ORDER BY created_at"))


def get_db_stats(conn: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    total = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    cols = conn.execute("SELECT COUNT(*) FROM collections").fetchone()[0]
    missing_preview = conn.execute("SELECT COUNT(*) FROM items WHERE preview_path IS NULL").fetchone()[0]
    return {"total_items": total, "total_collections": cols, "missing_preview": missing_preview}
