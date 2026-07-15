from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from cataloguecanvas import static_export


def _item(item_id: str = "apple-001", **over: Any) -> dict[str, Any]:
    rec: dict[str, Any] = {
        "id": item_id,
        "title": "A Title",
        "note": "",
        "tags": [],
        "width": 800,
        "height": 400,
    }
    rec.update(over)
    return rec


def _assets(*item_ids: str) -> dict[str, tuple[Path, str]]:
    return {i: (Path(f"/tmp/{i}.webp"), f"assets/{i}.webp") for i in item_ids}


def _render(style: str = "ledger", layout: str = "slide", items: list[dict[str, Any]] | None = None) -> str:
    items = items if items is not None else [_item()]
    return static_export._render_html(
        style, layout, "My Deck", "my-deck", "<p>Desc</p>", items, _assets(*[i["id"] for i in items])
    )


# --- layout and style are independent ---

@pytest.mark.parametrize("style", ["ledger", "kinetic", "brutalist", "riso"])
@pytest.mark.parametrize("layout", ["slide", "scroll"])
def test_root_carries_style_and_layout_independently(style, layout):
    html = _render(style, layout)
    assert f'data-portfolio-style="{style}"' in html
    assert f'data-portfolio-layout="{layout}"' in html


def test_scroll_css_is_present_and_print_rules_are_gated_to_slide():
    html = _render(layout="scroll")
    # The scroll block is keyed on the layout attribute alone, so it applies to
    # every theme; the print pagination only applies to slide decks.
    assert '.cc-deck[data-portfolio-layout="scroll"] .cc-deck__cover{min-height:auto}' in html
    assert '.cc-deck[data-portfolio-layout="slide"] .cc-deck__sec{page-break-after:always' in html


# --- section builders ---

def test_cover_renders_title_slug_and_count():
    html = static_export._render_cover("My Deck", "my-deck", "<p>Desc</p>", 3)
    assert "My Deck" in html
    assert "/p/my-deck" in html
    assert "Portfolio · 3 works" in html
    assert "<p>Desc</p>" in html


def test_cover_omits_description_block_when_empty():
    assert 'cc-deck__desc' not in static_export._render_cover("T", "s", "", 0)


def test_paged_index_splits_at_eight_per_page():
    items = [_item(f"item-{i:03d}") for i in range(9)]
    html = static_export._render_paged_index(items, lambda i: f"assets/{i}.webp", "my-deck", 9)
    assert html.count('<section class="cc-deck__sec cc-deck__index">') == 2
    assert "Works (cont.)" in html


def test_paged_index_falls_back_when_no_asset():
    html = static_export._render_paged_index([_item()], lambda _i: None, "s", 1)
    assert "no preview" in html


def test_kinetic_index_numbers_rows_and_links_to_plates():
    items = [_item("a-1"), _item("b-2")]
    html = static_export._render_kinetic_index(items, lambda i: f"assets/{i}.webp", 2)
    assert 'href="#work-a-1"' in html
    assert "01" in html and "02" in html


def test_plates_mark_wide_and_alternate_sides():
    items = [_item("a-1", width=800, height=400), _item("b-2", width=400, height=800)]
    html = static_export._render_plates(items, lambda i: f"assets/{i}.webp", 2)
    # First item is landscape -> wide; second is portrait and odd-indexed -> rev.
    assert "cc-deck__art--wide" in html
    assert "cc-deck__art--rev" in html


def test_plates_include_note_and_tags_only_when_present():
    with_meta = static_export._render_plates([_item(note="Hi", tags=["x"])], lambda i: "a.webp", 1)
    assert "<p>Hi</p>" in with_meta and "cc-deck__tags" in with_meta

    without = static_export._render_plates([_item()], lambda i: "a.webp", 1)
    assert "cc-deck__tags" not in without


def test_colophon_lists_every_work():
    items = [_item("a-1", title="One"), _item("b-2", title="Two")]
    html = static_export._render_colophon(items, "<p>D</p>", 2)
    assert "One" in html and "Two" in html
    assert "A portfolio of 2 works" in html


# --- kinetic-only markup ---

def test_kinetic_adds_marquee_and_follow_but_others_do_not():
    # Assert on markup, not bare class names: _CSS is inlined into every export
    # and always mentions the kinetic classes in its rules.
    marquee = '<section class="cc-deck__sec cc-deck__marquee"'
    follow = '<div class="cc-deck__follow"'

    kinetic = _render(style="kinetic")
    assert marquee in kinetic
    assert follow in kinetic
    assert '<div class="cc-deck__kindex">' in kinetic

    ledger = _render(style="ledger")
    assert marquee not in ledger
    assert follow not in ledger
    assert '<section class="cc-deck__sec cc-deck__index">' in ledger


def test_html_escapes_untrusted_text():
    html = _render(items=[_item(title='<script>alert(1)</script>')])
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
