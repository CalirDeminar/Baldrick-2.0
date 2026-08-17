"""Helpers bridging pyvips (memory-efficient large-image ops) and Pillow.

Map JPEGs/PNGs cannot be sampled randomly, so libvips would otherwise
decompress each file into ``TMPDIR`` on every open. We:

* point ``TMPDIR`` at ``tmp/scratch`` next to the app (source or frozen)
* transcode each source image once to a tiled TIFF under ``tmp/map-cache``
* reuse the opened image for the rest of the process
"""
from __future__ import annotations

import hashlib
import os
import threading
from pathlib import Path
from typing import Any

from PIL import Image

from shared import paths

# Pillow band mode by pyvips band count.
_MODES = {1: "L", 3: "RGB", 4: "RGBA"}

_RANDOM_ACCESS_SUFFIXES = {".tif", ".tiff", ".v"}
_CACHE_LOCK = threading.Lock()
_OPEN_IMAGES: dict[str, Any] = {}


def tmp_scratch_dir() -> Path:
    return paths.tmp_dir() / "scratch"


def map_cache_dir() -> Path:
    return paths.tmp_dir() / "map-cache"


def configure_tmpdir() -> Path:
    """Create the app tmp folders and send libvips disc spills to ``tmp/scratch``."""
    scratch = tmp_scratch_dir()
    scratch.mkdir(parents=True, exist_ok=True)
    map_cache_dir().mkdir(parents=True, exist_ok=True)
    os.environ["TMPDIR"] = str(scratch.resolve())
    return scratch


def clear_image_cache() -> None:
    """Drop in-memory image handles. On-disk tiled TIFF caches are kept."""
    with _CACHE_LOCK:
        _OPEN_IMAGES.clear()


def load_map_image(path: Path) -> Any:
    """Open a map image, decompressing each source file at most once.

    JPEG/PNG (and other sequential formats) are written to a tiled BigTIFF
    beside the app on first load. Later opens, including other cards in the
    same run, reuse that cache and the live pyvips image object.
    """
    configure_tmpdir()
    key = str(path.resolve())
    with _CACHE_LOCK:
        cached = _OPEN_IMAGES.get(key)
        if cached is not None:
            return cached
        image = _open_or_build_cache(path)
        _OPEN_IMAGES[key] = image
        return image


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


def _cache_path_for(source: Path) -> Path:
    stat = source.stat()
    digest = hashlib.sha1(str(source.resolve()).encode("utf-8")).hexdigest()[:8]
    name = f"{source.stem}-{digest}-{stat.st_mtime_ns}-{stat.st_size}.tif"
    return map_cache_dir() / name


def _remove_stale_caches(source: Path, keep: Path) -> None:
    digest = hashlib.sha1(str(source.resolve()).encode("utf-8")).hexdigest()[:8]
    prefix = f"{source.stem}-{digest}-"
    for old in map_cache_dir().glob(f"{prefix}*.tif"):
        if old != keep:
            old.unlink(missing_ok=True)


def _open_or_build_cache(path: Path) -> Any:
    import pyvips

    if path.suffix.lower() in _RANDOM_ACCESS_SUFFIXES:
        return pyvips.Image.new_from_file(str(path), access="random")

    cache_path = _cache_path_for(path)
    if cache_path.exists():
        try:
            return pyvips.Image.new_from_file(str(cache_path), access="random")
        except (pyvips.Error, OSError):
            cache_path.unlink(missing_ok=True)

    image = pyvips.Image.new_from_file(str(path), access="sequential")
    partial = cache_path.with_name(cache_path.name + ".partial")
    try:
        image.tiffsave(
            str(partial),
            tile=True,
            tile_width=256,
            tile_height=256,
            bigtiff=True,
            compression="none",
        )
        partial.replace(cache_path)
    except (pyvips.Error, OSError):
        partial.unlink(missing_ok=True)
        return pyvips.Image.new_from_file(str(path), access="random")

    _remove_stale_caches(path, cache_path)
    return pyvips.Image.new_from_file(str(cache_path), access="random")
