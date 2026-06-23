from __future__ import annotations

import re

import pytest

from cataloguecanvas import ids


def test_load_words_returns_lowercase_alpha():
    words = ids._load_words()
    assert words
    assert all(re.match(r"^[a-z]+$", w) for w in words[:50])


def test_generate_item_id_shape(conn):
    item_id = ids.generate_item_id(conn)
    assert re.match(r"^[a-z]+-\d{3}$", item_id)


def test_generate_item_id_avoids_collision(conn, monkeypatch):
    # Force the first candidate to already exist, second to be free.
    seen = {"count": 0}

    def fake_exists(_conn, candidate):
        seen["count"] += 1
        return seen["count"] == 1  # only the first candidate "exists"

    monkeypatch.setattr(ids, "id_exists", fake_exists)
    item_id = ids.generate_item_id(conn)
    assert re.match(r"^[a-z]+-\d{3}$", item_id)
    assert seen["count"] >= 2


def test_generate_item_id_exhausts(conn, monkeypatch):
    monkeypatch.setattr(ids, "id_exists", lambda *a: True)
    with pytest.raises(RuntimeError, match="could not generate a unique item id"):
        ids.generate_item_id(conn)


def test_generate_portfolio_slug_shape():
    slug = ids.generate_portfolio_slug(lambda _s: False)
    assert re.match(r"^[a-z]+-[a-z]+-[a-z]+$", slug)


def test_generate_portfolio_slug_exhausts():
    with pytest.raises(RuntimeError, match="could not generate a unique slug"):
        ids.generate_portfolio_slug(lambda _s: True)
