from __future__ import annotations
import random
import re
import sqlite3
from pathlib import Path

from .db import id_exists

WORDS_PATHS = [
    Path("/usr/share/dict/words"),
    Path(__file__).resolve().parent / "wordlist.txt",
]
_WORD_RE = re.compile(r"^[a-z]+$")
MAX_ATTEMPTS = 100


def _load_words() -> list[str]:
    for path in WORDS_PATHS:
        if path.exists():
            words = path.read_text(encoding="utf-8", errors="ignore").splitlines()
            filtered = [w.lower() for w in words if _WORD_RE.match(w.lower())]
            if filtered:
                return filtered
    raise RuntimeError("no wordlist available for item id generation")


def generate_item_id(conn: sqlite3.Connection) -> str:
    """Generate a unique item ID of the form '<word>-<NNN>'."""
    words = _load_words()
    for _ in range(MAX_ATTEMPTS):
        candidate = f"{random.choice(words)}-{random.randint(0, 999):03d}"
        if not id_exists(conn, candidate):
            return candidate
    raise RuntimeError(f"could not generate a unique item id after {MAX_ATTEMPTS} attempts")


def generate_portfolio_slug(exists) -> str:
    """Generate a slug of the form '<word>-<word>-<word>'."""
    words = _load_words()
    for _ in range(MAX_ATTEMPTS):
        candidate = "-".join(random.choice(words) for _ in range(3))
        if not exists(candidate):
            return candidate
    raise RuntimeError(f"could not generate a unique slug after {MAX_ATTEMPTS} attempts")
