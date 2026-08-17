"""Centralised filesystem path resolution.

Baldrick can run either from source (during development) or as a frozen
PyInstaller ``onedir`` bundle. Read-only assets that ship with the app
(the ``map_data`` folder) live next to the bundled code, while user-editable
files (``config.yaml``, ``routes``, ``fuel_maps``, rendered ``output`` and
``tmp``) live next to the executable so a user can edit them after install.
"""
from __future__ import annotations

import sys
from pathlib import Path

_IS_FROZEN = getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


def bundle_dir() -> Path:
    """Directory containing read-only bundled assets (e.g. ``map_data``)."""
    if _IS_FROZEN:
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parents[2]


def app_dir() -> Path:
    """Directory for user-editable files (config, routes, fuel maps, output, tmp)."""
    if _IS_FROZEN:
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def assets_dir() -> Path:
    return bundle_dir() / "assets"


def font_path() -> Path:
    return assets_dir() / "fonts" / "Aileron-Regular.otf"


def map_data_dir() -> Path:
    return bundle_dir() / "map_data"


def map_image_dir() -> Path:
    return map_data_dir() / "image_files"


def routes_dir() -> Path:
    return app_dir() / "routes"


def fuel_maps_dir() -> Path:
    return app_dir() / "fuel_maps"


def config_path() -> Path:
    return app_dir() / "config.yaml"


def output_dir() -> Path:
    return app_dir() / "output"


def tmp_dir() -> Path:
    """Writable scratch and map-image cache, next to the executable / project root."""
    return app_dir() / "tmp"
