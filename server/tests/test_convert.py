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
