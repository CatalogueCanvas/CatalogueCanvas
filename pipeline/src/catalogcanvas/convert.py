from __future__ import annotations
import io
from pathlib import Path

from PIL import Image


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
