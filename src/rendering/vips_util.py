"""Helpers bridging pyvips (memory-efficient large-image ops) and Pillow."""
from __future__ import annotations

from typing import Any

from PIL import Image

# Pillow band mode by pyvips band count.
_MODES = {1: "L", 3: "RGB", 4: "RGBA"}


def vips_to_pil(image: Any) -> Image.Image:
    """Convert an in-memory pyvips image (uchar) to a Pillow image."""
    if image.format != "uchar":
        image = image.cast("uchar")
    mode = _MODES.get(image.bands)
    if mode is None:
        image = image.colourspace("srgb")
        mode = _MODES.get(image.bands, "RGB")
    buffer = image.write_to_memory()
    return Image.frombuffer(mode, (image.width, image.height), buffer, "raw", mode, 0, 1)


def ensure_rgb(image: Any) -> Any:
    if image.bands == 4:
        return image.flatten()
    if image.bands == 1:
        return image.colourspace("srgb")
    return image
