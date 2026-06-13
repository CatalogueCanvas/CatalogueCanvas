from __future__ import annotations
import random
import re
from pathlib import Path

import duckdb

from .db import id_exists

WORDS_PATH = Path("/usr/share/dict/words")
_WORD_RE = re.compile(r"^[a-z]+$")
MAX_ATTEMPTS = 100


def _load_words() -> list[str]:
    words = WORDS_PATH.read_text(encoding="utf-8", errors="ignore").splitlines()
    return [w.lower() for w in words if _WORD_RE.match(w.lower())]


def generate_item_id(conn: duckdb.DuckDBPyConnection) -> str:
    """Generate a unique item ID of the form '<word>-<NNN>'."""
    words = _load_words()
    for _ in range(MAX_ATTEMPTS):
        candidate = f"{random.choice(words)}-{random.randint(0, 999):03d}"
        if not id_exists(conn, candidate):
            return candidate
    raise RuntimeError(f"could not generate a unique item id after {MAX_ATTEMPTS} attempts")
