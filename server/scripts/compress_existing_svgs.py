"""One-off migration: lz4-compress existing .svg files in item storage.

Usage: uv run python scripts/compress_existing_svgs.py
"""
from __future__ import annotations
import json
import os
import sqlite3
from pathlib import Path

import lz4.frame

if "CC_DATA_DIR" not in os.environ:
    default_data_dir = Path(__file__).resolve().parents[2] / "data"
    if default_data_dir.is_dir():
        os.environ["CC_DATA_DIR"] = str(default_data_dir)

from cataloguecanvas.settings import settings


def main() -> None:
    conn = sqlite3.connect(str(settings.db_path))
    conn.row_factory = sqlite3.Row

    rows = conn.execute("SELECT id, other_files FROM items").fetchall()
    changed = 0
    for row in rows:
        other_files = json.loads(row["other_files"] or "[]")
        new_files = []
        item_changed = False

        for f in other_files:
            if not f.lower().endswith(".svg"):
                new_files.append(f)
                continue

            svg_path = settings.storage_dir / f
            if not svg_path.exists():
                new_files.append(f)
                continue

            compressed_path = svg_path.with_name(svg_path.name + ".lz4")
            compressed_path.write_bytes(lz4.frame.compress(svg_path.read_bytes()))
            svg_path.unlink()

            new_files.append(str(compressed_path.relative_to(settings.storage_dir)))
            item_changed = True

        if item_changed:
            conn.execute(
                "UPDATE items SET other_files = ? WHERE id = ?",
                (json.dumps(new_files), row["id"]),
            )
            changed += 1
            print(f"compressed SVG(s) for item {row['id']}")

    conn.commit()
    conn.close()
    print(f"done: {changed} item(s) updated")


if __name__ == "__main__":
    main()
