from __future__ import annotations
import io
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

Image.MAX_IMAGE_PIXELS = 128_000_000  # ~128MP cap, guards against decompression bombs


def _svg_intrinsic_size(tree) -> tuple[float, float] | None:
    """Best-effort (width, height) in user units for a parsed cairosvg Tree.

    Only plain numbers and explicit `px` are resolved here; percentages and
    physical units (pt/mm/in) need a live cairo surface to resolve, which does
    not exist before rendering. Falls back to the viewBox, then gives up by
    returning None so the caller can render at the plain scale factor.
    """
    def _px(raw: str | None) -> float | None:
        if not raw:
            return None
        text = raw.strip().removesuffix("px").strip()
        try:
            value = float(text)
        except ValueError:
            return None
        return value if value > 0 else None

    width, height = _px(tree.get("width")), _px(tree.get("height"))
    if width and height:
        return width, height

    viewbox = tree.get("viewBox")
    if viewbox:
        parts = re.sub(r"[\s,]+", " ", viewbox.strip()).split()
        if len(parts) == 4:
            try:
                vb_width, vb_height = float(parts[2]), float(parts[3])
            except ValueError:
                return None
            if vb_width > 0 and vb_height > 0:
                return width or vb_width, height or vb_height
    return None


def _raster_kwargs(tree, scale: float, max_edge: int | None) -> dict[str, float | int]:
    """cairosvg render arguments that keep the output within `max_edge` px.

    Rasterization cost grows with the square of the output size, so a blind
    scale multiplier on a large SVG is unbounded work. When the scaled result
    would exceed the cap, pin the longest edge instead — cairosvg derives the
    other edge itself, preserving the aspect ratio. Never upscales past what
    `scale` asked for.
    """
    if not max_edge or max_edge <= 0:
        return {"scale": scale}

    size = _svg_intrinsic_size(tree)
    if size is None:
        return {"scale": scale}

    width, height = size[0] * scale, size[1] * scale
    if max(width, height) <= max_edge:
        return {"scale": scale}

    if width >= height:
        return {"output_width": max_edge}
    return {"output_height": max_edge}


def to_webp(
    image_bytes: bytes,
    mime_type: str,
    out_path: Path,
    scale: float = 2.0,
    max_edge: int | None = None,
) -> Path:
    """Convert image bytes (svg, png, jpeg, or tiff) to a webp file at out_path.

    `max_edge` caps the longest edge of a rendered SVG in px; None or 0 renders
    at the plain `scale` factor.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if mime_type == "image/svg+xml":
        import cairosvg
        from cairosvg.parser import Tree
        # Parse once up front purely to read the intrinsic size; svg2png does
        # its own parse, but that is trivial next to the rasterization itself.
        tree = Tree(bytestring=image_bytes)
        png_bytes = cairosvg.svg2png(
            bytestring=image_bytes, **_raster_kwargs(tree, scale, max_edge)
        )
        img = Image.open(io.BytesIO(png_bytes))
    else:
        img = Image.open(io.BytesIO(image_bytes))

    img.save(out_path, format="WEBP", quality=85)
    return out_path


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Best-effort sans-serif font; fall back to Pillow's bundled bitmap font."""
    for name in ("Arial.ttf", "Helvetica.ttf", "DejaVuSans.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _burn_watermark(img: Image.Image, text: str, *, margin_ratio: float = 0.025) -> Image.Image:
    """Composite semi-transparent white `text` into the bottom-right of an RGBA image.

    Mirrors the ImageMagick southeast-gravity overlay: white at 50% alpha, an
    offset margin scaled to the image. Returns a new RGBA image.
    """
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Font size ~4% of the shorter edge keeps the mark proportional across sizes.
    font_size = max(14, int(min(img.width, img.height) * 0.04))
    font = _load_font(font_size)

    bbox = draw.textbbox((0, 0), text, font=font)
    text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    margin = int(min(img.width, img.height) * margin_ratio)
    x = img.width - text_w - margin - bbox[0]
    y = img.height - text_h - margin - bbox[1]

    draw.text((x, y), text, font=font, fill=(255, 255, 255, 128))
    return Image.alpha_composite(img, overlay)


def watermark_webp(image_bytes: bytes, text: str, *, margin_ratio: float = 0.025) -> bytes:
    """Burn semi-transparent white `text` into the bottom-right of a webp image.

    Empty text returns the input unchanged. Output is webp bytes (quality 85).
    """
    if not text.strip():
        return image_bytes

    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    out = _burn_watermark(img, text, margin_ratio=margin_ratio).convert("RGB")
    buf = io.BytesIO()
    out.save(buf, format="WEBP", quality=85)
    return buf.getvalue()


def process_export_webp(
    image_bytes: bytes,
    *,
    quality: int = 85,
    max_edge: int | None = None,
    watermark: str = "",
) -> bytes:
    """Downscale, optionally watermark, and re-encode an image as webp bytes.

    `max_edge` (longest-edge cap in px) downscales with LANCZOS when the image
    is larger; `None` keeps the original size. `quality` is clamped 40..95.
    Watermark is burned bottom-right when non-empty (scaled to the final size).
    """
    quality = max(40, min(95, quality))
    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")

    if max_edge and max(img.width, img.height) > max_edge:
        img.thumbnail((max_edge, max_edge), Image.LANCZOS)

    if watermark.strip():
        img = _burn_watermark(img, watermark)

    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="WEBP", quality=quality)
    return buf.getvalue()
