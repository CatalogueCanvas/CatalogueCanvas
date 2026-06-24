from __future__ import annotations
import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

Image.MAX_IMAGE_PIXELS = 128_000_000  # ~128MP cap, guards against decompression bombs


def to_webp(image_bytes: bytes, mime_type: str, out_path: Path, scale: float = 2.0) -> Path:
    """Convert image bytes (svg, png, jpeg, or tiff) to a webp file at out_path."""
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if mime_type == "image/svg+xml":
        import cairosvg
        png_bytes = cairosvg.svg2png(bytestring=image_bytes, scale=scale)
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
