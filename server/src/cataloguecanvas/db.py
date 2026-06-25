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

CREATE VIRTUAL TABLE IF NOT EXISTS items_fts USING fts5(
    item_id UNINDEXED, title, note, tags, meta,
    tokenize = 'unicode61 remove_diacritics 2'
);

CREATE TABLE IF NOT EXISTS collections (
    id            TEXT PRIMARY KEY,
    title         TEXT,
    description   TEXT,
    cover_item_id TEXT,
    is_system     INTEGER NOT NULL DEFAULT 0,
    visibility    TEXT NOT NULL DEFAULT 'admin',
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
    visibility  TEXT NOT NULL DEFAULT 'admin',
    style       TEXT NOT NULL DEFAULT 'ledger',
    watermark_enabled INTEGER NOT NULL DEFAULT 0,
    watermark_text    TEXT NOT NULL DEFAULT '',
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS admin (
    id            INTEGER PRIMARY KEY CHECK (id = 1),
    password_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL CHECK (role IN ('admin', 'reader')),
    created_at    TEXT DEFAULT (datetime('now'))
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

CREATE TABLE IF NOT EXISTS sessions (
    sid        TEXT PRIMARY KEY,
    role       TEXT NOT NULL,
    username   TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS login_attempts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    scope       TEXT NOT NULL,
    attempted_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_login_attempts_scope ON login_attempts(scope, attempted_at);
"""

# Allow-lists of valid column identifiers for the dynamic-column upserts below.
# Records are always built server-side, but validating the keys here keeps the
# SQL string construction provably safe regardless of caller.
_ITEM_COLUMNS = frozenset({
    "id", "content_hash", "title", "note", "mime_type", "preview_path",
    "other_files", "tags", "collection_id", "raw_meta", "ingested_at",
    "imported_at", "width", "height", "library_id",
})
_PORTFOLIO_COLUMNS = frozenset({
    "id", "slug", "title", "description", "item_ids", "is_public",
    "visibility", "style", "watermark_enabled", "watermark_text", "created_at",
})


def _check_columns(cols: list[str], allowed: frozenset[str]) -> None:
    """Reject any column name that is not a known schema identifier."""
    unknown = [c for c in cols if c not in allowed]
    if unknown:
        raise ValueError(f"unknown column(s): {', '.join(sorted(unknown))}")


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
    # Fixed DDL statements (no interpolation) for columns added after v1.
    item_column_ddl = {
        "width": "ALTER TABLE items ADD COLUMN width INTEGER",
        "height": "ALTER TABLE items ADD COLUMN height INTEGER",
    }
    for col, ddl in item_column_ddl.items():
        if col not in existing_cols:
            conn.execute(ddl)

    collection_cols = {row["name"] for row in conn.execute("PRAGMA table_info(collections)")}
    if "is_system" not in collection_cols:
        conn.execute("ALTER TABLE collections ADD COLUMN is_system INTEGER NOT NULL DEFAULT 0")
    if "visibility" not in collection_cols:
        # Existing collections default to admin-only so readers don't suddenly
        # gain access to data created before visibility control existed.
        conn.execute("ALTER TABLE collections ADD COLUMN visibility TEXT NOT NULL DEFAULT 'admin'")

    portfolio_cols = {row["name"] for row in conn.execute("PRAGMA table_info(portfolios)")}
    if "visibility" not in portfolio_cols:
        conn.execute("ALTER TABLE portfolios ADD COLUMN visibility TEXT NOT NULL DEFAULT 'admin'")
    if "style" not in portfolio_cols:
        conn.execute("ALTER TABLE portfolios ADD COLUMN style TEXT NOT NULL DEFAULT 'ledger'")
    if "watermark_enabled" not in portfolio_cols:
        conn.execute("ALTER TABLE portfolios ADD COLUMN watermark_enabled INTEGER NOT NULL DEFAULT 0")
    if "watermark_text" not in portfolio_cols:
        conn.execute("ALTER TABLE portfolios ADD COLUMN watermark_text TEXT NOT NULL DEFAULT ''")

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

    # Seed the admin user from the legacy single-admin hash so existing
    # deployments keep working when multi-user mode is later enabled.
    user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if user_count == 0:
        admin_hash = conn.execute("SELECT password_hash FROM admin WHERE id = 1").fetchone()
        if admin_hash:
            conn.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (?, ?, 'admin')",
                (settings.admin_username, admin_hash["password_hash"]),
            )

    # Backfill the FTS index for pre-existing items (migration for older DBs).
    fts_count = conn.execute("SELECT COUNT(*) FROM items_fts").fetchone()[0]
    item_count = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    if fts_count == 0 and item_count > 0:
        for row in conn.execute("SELECT * FROM items").fetchall():
            index_item(conn, _row_to_dict(row))

    conn.commit()


def _dump(v: Any) -> Any:
    if isinstance(v, (dict, list)):
        return json.dumps(v)
    return v


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


# --- full-text search ---

def flatten_meta(value: Any) -> str:
    """Recursively collect keys and scalar values from a nested dict/list into a
    single space-joined string, so arbitrary metadata.json content is searchable."""
    parts: list[str] = []

    def walk(v: Any) -> None:
        if isinstance(v, dict):
            for k, sub in v.items():
                parts.append(str(k))
                walk(sub)
        elif isinstance(v, list):
            for sub in v:
                walk(sub)
        elif v is not None:
            parts.append(str(v))

    walk(value)
    return " ".join(parts)


def _coerce(value: Any) -> Any:
    """Decode a possibly JSON-encoded column into a Python object."""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def index_item(conn: sqlite3.Connection, item: dict[str, Any]) -> None:
    """Upsert the FTS row for an item (delete-then-insert; FTS5 has no UPSERT)."""
    item_id = item["id"]
    tags = _coerce(item.get("tags")) or []
    tags_text = " ".join(str(t) for t in tags) if isinstance(tags, list) else str(tags)
    meta_text = flatten_meta(_coerce(item.get("raw_meta")) or {})
    conn.execute("DELETE FROM items_fts WHERE item_id = ?", (item_id,))
    conn.execute(
        "INSERT INTO items_fts (item_id, title, note, tags, meta) VALUES (?, ?, ?, ?, ?)",
        (item_id, item.get("title") or "", item.get("note") or "", tags_text, meta_text),
    )


def unindex_item(conn: sqlite3.Connection, item_id: str) -> None:
    conn.execute("DELETE FROM items_fts WHERE item_id = ?", (item_id,))


def _fts_query(raw: str) -> str:
    """Turn free user input into a safe FTS5 MATCH expression: each token is
    quoted (so punctuation can't break syntax) with a prefix wildcard."""
    tokens = [t for t in raw.replace('"', " ").split() if t]
    return " ".join(f'"{t}"*' for t in tokens)


def search_items(conn: sqlite3.Connection, query: str) -> list[dict[str, Any]]:
    """Full-text search across title/note/tags/flattened raw_meta, ranked by
    relevance. Empty query returns all items (same shape as get_all_items)."""
    match = _fts_query(query)
    if not match:
        return get_all_items(conn)
    rows = conn.execute(
        """
        SELECT i.* FROM items i
        JOIN items_fts f ON f.item_id = i.id
        WHERE items_fts MATCH ?
        ORDER BY f.rank
        """,
        (match,),
    ).fetchall()
    items = [_row_to_dict(r) for r in rows]
    membership = _collection_membership(conn)
    for item in items:
        item["collection_ids"] = membership.get(item["id"], [])
    return items


def _collection_membership(conn: sqlite3.Connection) -> dict[str, list[str]]:
    membership: dict[str, list[str]] = {}
    for row in conn.execute("SELECT item_id, collection_id FROM item_collections"):
        membership.setdefault(row["item_id"], []).append(row["collection_id"])
    return membership


# --- items ---

def hash_exists(conn: sqlite3.Connection, content_hash: str) -> Optional[str]:
    row = conn.execute("SELECT id FROM items WHERE content_hash = ?", (content_hash,)).fetchone()
    return row["id"] if row else None


def id_exists(conn: sqlite3.Connection, item_id: str) -> bool:
    row = conn.execute("SELECT 1 FROM items WHERE id = ?", (item_id,)).fetchone()
    return row is not None


def upsert_item(conn: sqlite3.Connection, record: dict[str, Any]) -> None:
    cols = list(record.keys())
    _check_columns(cols, _ITEM_COLUMNS)
    placeholders = ", ".join(["?" for _ in cols])
    col_names = ", ".join(cols)
    updates = ", ".join(f"{c} = excluded.{c}" for c in cols if c != "id")
    sql = f"""
        INSERT INTO items ({col_names}) VALUES ({placeholders})
        ON CONFLICT (id) DO UPDATE SET {updates}
    """
    values = [_dump(v) for v in record.values()]
    conn.execute(sql, values)  # nosec B608 — columns validated by _check_columns
    index_item(conn, record)
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
    membership = _collection_membership(conn)
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
    conn.execute(f"UPDATE items SET {set_clause} WHERE id = ?", (*values, item_id))  # nosec B608 — columns from hardcoded allowlist
    updated = get_item(conn, item_id)
    if updated:
        index_item(conn, updated)
    conn.commit()
    return updated


def delete_item(conn: sqlite3.Connection, item_id: str) -> None:
    conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
    unindex_item(conn, item_id)
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
        INSERT INTO collections (id, title, description, cover_item_id, is_system, visibility)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT (id) DO UPDATE SET
            title = excluded.title,
            description = excluded.description,
            cover_item_id = excluded.cover_item_id,
            visibility = excluded.visibility
    """, (col["id"], col.get("title", ""), col.get("description", ""), col.get("cover_item_id"), col.get("is_system", 0), col.get("visibility", "admin")))
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
    _check_columns(cols, _PORTFOLIO_COLUMNS)
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


def _parse_json_list(raw: Any) -> list:
    if not raw:
        return []
    if not isinstance(raw, str):
        return raw if isinstance(raw, list) else []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def get_public_item_ids(conn: sqlite3.Connection) -> set[str]:
    """Return the set of item IDs reachable through any public portfolio.

    Used to authorize anonymous file serving on the public storage route so it
    only exposes files belonging to items an operator has explicitly published.
    """
    rows = conn.execute("SELECT item_ids FROM portfolios WHERE is_public = 1").fetchall()
    ids: set[str] = set()
    for row in rows:
        for item_id in _parse_json_list(row["item_ids"]):
            if isinstance(item_id, str):
                ids.add(item_id)
    return ids


def is_public_storage_path(conn: sqlite3.Connection, library_id: str, rel_path: str) -> bool:
    """Whether (library_id, rel_path) is the preview file of an item that is
    published through a public portfolio.

    Only the webp preview is exposed anonymously; attachments stay session-gated.
    """
    public_ids = get_public_item_ids(conn)
    if not public_ids:
        return False
    # Look up each candidate by primary key (parameterized) and match in Python,
    # avoiding a dynamically built IN (...) clause.
    for item_id in public_ids:
        row = conn.execute(
            "SELECT library_id, preview_path FROM items WHERE id = ?",
            (item_id,),
        ).fetchone()
        if row and row["library_id"] == library_id and row["preview_path"] == rel_path:
            return True
    return False


# --- sessions ---

def create_session(conn: sqlite3.Connection, sid: str, role: str, username: Optional[str]) -> None:
    conn.execute(
        "INSERT INTO sessions (sid, role, username) VALUES (?, ?, ?)",
        (sid, role, username),
    )
    conn.commit()


def session_exists(conn: sqlite3.Connection, sid: str) -> bool:
    row = conn.execute("SELECT 1 FROM sessions WHERE sid = ?", (sid,)).fetchone()
    return row is not None


def delete_session(conn: sqlite3.Connection, sid: str) -> None:
    conn.execute("DELETE FROM sessions WHERE sid = ?", (sid,))
    conn.commit()


# --- login throttle (durable, survives restart) ---

def count_recent_login_failures(conn: sqlite3.Connection, scope: str, since: float) -> int:
    row = conn.execute(
        "SELECT COUNT(*) FROM login_attempts WHERE scope = ? AND attempted_at >= ?",
        (scope, since),
    ).fetchone()
    return int(row[0])


def record_login_failure(conn: sqlite3.Connection, scope: str, now: float) -> None:
    conn.execute(
        "INSERT INTO login_attempts (scope, attempted_at) VALUES (?, ?)",
        (scope, now),
    )
    conn.commit()


def clear_login_failures(conn: sqlite3.Connection, scope: str) -> None:
    conn.execute("DELETE FROM login_attempts WHERE scope = ?", (scope,))
    conn.commit()


def prune_login_failures(conn: sqlite3.Connection, before: float) -> None:
    conn.execute("DELETE FROM login_attempts WHERE attempted_at < ?", (before,))
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


# --- users ---

def get_user_by_username(conn: sqlite3.Connection, username: str) -> Optional[dict[str, Any]]:
    row = conn.execute(
        "SELECT id, username, password_hash, role, created_at FROM users WHERE username = ?",
        (username,),
    ).fetchone()
    return dict(row) if row else None


def get_user(conn: sqlite3.Connection, user_id: int) -> Optional[dict[str, Any]]:
    row = conn.execute(
        "SELECT id, username, password_hash, role, created_at FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    return dict(row) if row else None


def list_users(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT id, username, role, created_at FROM users ORDER BY id"
    ).fetchall()
    return [dict(r) for r in rows]


def create_user(conn: sqlite3.Connection, username: str, password_hash: str, role: str) -> int:
    cur = conn.execute(
        "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
        (username, password_hash, role),
    )
    conn.commit()
    return int(cur.lastrowid)


def update_user(
    conn: sqlite3.Connection,
    user_id: int,
    *,
    username: Optional[str] = None,
    password_hash: Optional[str] = None,
    role: Optional[str] = None,
) -> None:
    sets: list[str] = []
    params: list[Any] = []
    if username is not None:
        sets.append("username = ?")
        params.append(username)
    if password_hash is not None:
        sets.append("password_hash = ?")
        params.append(password_hash)
    if role is not None:
        sets.append("role = ?")
        params.append(role)
    if not sets:
        return
    params.append(user_id)
    conn.execute(f"UPDATE users SET {', '.join(sets)} WHERE id = ?", params)  # nosec B608 — columns are hardcoded literals
    conn.commit()


def delete_user(conn: sqlite3.Connection, user_id: int) -> None:
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()


def count_admins(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'").fetchone()[0]


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
        conn.execute(f"UPDATE libraries SET {set_clause} WHERE id = ?", (*fields.values(), lib_id))  # nosec B608 — columns from hardcoded allowlist
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
