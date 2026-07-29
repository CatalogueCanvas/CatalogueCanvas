from __future__ import annotations

import io

import pytest
from PIL import Image

from cataloguecanvas import convert


def _png_bytes(size=(64, 48), color=(120, 30, 30)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


def _webp_bytes(size=(64, 48), color=(10, 80, 120)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="WEBP")
    return buf.getvalue()


def _open(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data))


# --- to_webp ---

def test_to_webp_from_png(tmp_path):
    out = tmp_path / "nested" / "out.webp"
    result = convert.to_webp(_png_bytes(), "image/png", out)
    assert result == out
    assert out.exists()
    assert _open(out.read_bytes()).format == "WEBP"


def _cairo_available() -> bool:
    # cairosvg pulls in cairocffi, which loads the native cairo lib at import
    # time and raises OSError (not ImportError) when it's missing — so a plain
    # importorskip isn't enough.
    try:
        import cairosvg  # noqa: F401
    except (ImportError, OSError):
        return False
    return True


@pytest.mark.skipif(not _cairo_available(), reason="native cairo library unavailable")
def test_to_webp_from_svg(tmp_path):
    svg = b'<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20">' \
          b'<rect width="20" height="20" fill="red"/></svg>'
    out = tmp_path / "svg.webp"
    convert.to_webp(svg, "image/svg+xml", out, scale=1.0)
    assert _open(out.read_bytes()).format == "WEBP"


def _svg_partial(dimension: str, viewbox: str) -> bytes:
    """An SVG with only one of width/height set, plus a viewBox."""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" {dimension} viewBox="{viewbox}">'
        f'<rect width="100%" height="100%" fill="red"/></svg>'
    ).encode()


def _svg(width: str, height: str, viewbox: str | None = None) -> bytes:
    vb = f' viewBox="{viewbox}"' if viewbox else ""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"{vb}>'
        f'<rect width="100%" height="100%" fill="red"/></svg>'
    ).encode()


# --- _svg_intrinsic_size / _raster_kwargs (no cairo needed) ---

def test_raster_kwargs_no_cap_keeps_scale():
    tree = {"width": "4000", "height": "4000"}
    assert convert._raster_kwargs(tree, 2.5, None) == {"scale": 2.5}
    assert convert._raster_kwargs(tree, 2.5, 0) == {"scale": 2.5}


def test_raster_kwargs_caps_longest_edge():
    # 4000x2000 at scale 2.5 would be 10000px wide — pin the width instead.
    assert convert._raster_kwargs({"width": "4000", "height": "2000"}, 2.5, 1000) == {"output_width": 1000}
    # Portrait: the height is the longest edge.
    assert convert._raster_kwargs({"width": "2000", "height": "4000"}, 2.5, 1000) == {"output_height": 1000}


def test_raster_kwargs_leaves_small_svg_alone():
    # 100x100 at scale 2.5 is 250px, well under the cap — must not upscale.
    assert convert._raster_kwargs({"width": "100", "height": "100"}, 2.5, 1000) == {"scale": 2.5}


def test_raster_kwargs_falls_back_when_size_unresolvable():
    # Percentages and physical units need a live cairo surface to resolve.
    assert convert._raster_kwargs({"width": "100%", "height": "100%"}, 2.0, 500) == {"scale": 2.0}
    assert convert._raster_kwargs({"width": "210mm", "height": "297mm"}, 2.0, 500) == {"scale": 2.0}
    assert convert._raster_kwargs({}, 2.0, 500) == {"scale": 2.0}


def test_raster_kwargs_uses_viewbox_when_no_dimensions():
    tree = {"width": "100%", "height": "100%", "viewBox": "0 0 4000 2000"}
    assert convert._raster_kwargs(tree, 2.5, 1000) == {"output_width": 1000}


def test_intrinsic_size_strips_px_and_rejects_junk():
    assert convert._svg_intrinsic_size({"width": "400px", "height": "200px"}) == (400.0, 200.0)
    assert convert._svg_intrinsic_size({"width": "0", "height": "0"}) is None
    assert convert._svg_intrinsic_size({"width": "abc", "height": "def"}) is None


# --- to_webp raster cap (needs cairo) ---

@pytest.mark.skipif(not _cairo_available(), reason="native cairo library unavailable")
def test_to_webp_svg_respects_max_edge(tmp_path):
    out = tmp_path / "big.webp"
    convert.to_webp(_svg("4000", "4000"), "image/svg+xml", out, scale=2.5, max_edge=1000)
    img = _open(out.read_bytes())
    assert max(img.width, img.height) <= 1000


@pytest.mark.skipif(not _cairo_available(), reason="native cairo library unavailable")
def test_to_webp_svg_max_edge_preserves_aspect_ratio(tmp_path):
    out = tmp_path / "wide.webp"
    convert.to_webp(_svg("4000", "2000"), "image/svg+xml", out, scale=2.5, max_edge=1000)
    img = _open(out.read_bytes())
    assert (img.width, img.height) == (1000, 500)


@pytest.mark.skipif(not _cairo_available(), reason="native cairo library unavailable")
def test_to_webp_svg_does_not_upscale_small_input(tmp_path):
    out = tmp_path / "small.webp"
    convert.to_webp(_svg("100", "100"), "image/svg+xml", out, scale=2.0, max_edge=1000)
    img = _open(out.read_bytes())
    assert (img.width, img.height) == (200, 200)


@pytest.mark.skipif(not _cairo_available(), reason="native cairo library unavailable")
def test_to_webp_svg_partial_dimensions_stay_capped(tmp_path):
    # Only one of width/height set alongside a viewBox. cairosvg resolves the
    # missing axis itself (oddly, but that predates the cap) — what matters here
    # is that the output still respects max_edge rather than escaping it.
    for name, svg in (
        ("w", _svg_partial('width="4000"', "0 0 100 50")),
        ("h", _svg_partial('height="4000"', "0 0 100 50")),
    ):
        out = tmp_path / f"{name}.webp"
        convert.to_webp(svg, "image/svg+xml", out, scale=2.5, max_edge=1000)
        img = _open(out.read_bytes())
        assert max(img.width, img.height) <= 1000


@pytest.mark.skipif(not _cairo_available(), reason="native cairo library unavailable")
def test_to_webp_svg_percentage_size_still_renders(tmp_path):
    out = tmp_path / "pct.webp"
    convert.to_webp(_svg("100%", "100%", viewbox="0 0 50 25"), "image/svg+xml", out, scale=2.0, max_edge=1000)
    assert _open(out.read_bytes()).format == "WEBP"


# --- watermark_webp ---

def test_watermark_empty_text_passthrough():
    data = _webp_bytes()
    assert convert.watermark_webp(data, "   ") is data


def test_watermark_returns_webp():
    out = convert.watermark_webp(_webp_bytes(), "© me")
    assert _open(out).format == "WEBP"


# --- process_export_webp ---

def test_process_export_clamps_quality():
    # very low and very high quality should still produce valid webp output
    low = convert.process_export_webp(_webp_bytes(), quality=1)
    high = convert.process_export_webp(_webp_bytes(), quality=200)
    assert _open(low).format == "WEBP"
    assert _open(high).format == "WEBP"


def test_process_export_downscales():
    big = _webp_bytes(size=(400, 200))
    out = convert.process_export_webp(big, max_edge=100)
    img = _open(out)
    assert max(img.width, img.height) <= 100


def test_process_export_no_resize_when_small():
    out = convert.process_export_webp(_webp_bytes(size=(50, 50)), max_edge=100)
    img = _open(out)
    assert (img.width, img.height) == (50, 50)


def test_process_export_with_watermark():
    out = convert.process_export_webp(_webp_bytes(size=(200, 200)), watermark="mark")
    assert _open(out).format == "WEBP"


def test_load_font_returns_font():
    font = convert._load_font(18)
    assert font is not None
