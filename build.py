"""Build the distributable PyInstaller bundle.

Produces ``dist/baldrick`` containing ``baldrick.exe`` plus the user-editable
files (``config.yaml``, ``routes/``, ``fuel_maps/``) alongside it. The large
read-only ``map_data`` folder is bundled inside the executable's ``_internal``
directory by ``baldrick.spec``.

Also writes two release zips under ``dist/``:

- ``baldrick-{version}.zip`` — full application bundle
- ``baldrick-maps-{version}.zip`` — shareable map YAML and images only
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from shared.map_packaging import MapPackagingError, iter_shareable_map_files, stage_map_data

DIST = ROOT / "dist" / "baldrick"
MAP_DATA_SRC = ROOT / "map_data"
MAP_DATA_STAGE = ROOT / "build" / "map_data_bundle"


def read_version() -> str:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', pyproject, re.MULTILINE)
    if not match:
        raise RuntimeError("Could not read project version from pyproject.toml")
    return match.group(1)


def remove_dist_zips(version: str) -> None:
    dist_dir = ROOT / "dist"
    for pattern in (f"baldrick-{version}.zip", f"baldrick-maps-{version}.zip", "baldrick.zip"):
        path = dist_dir / pattern
        if path.exists():
            path.unlink()


def zip_directory(source_dir: Path, zip_path: Path) -> None:
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in sorted(source_dir.rglob("*")):
            if file_path.is_file():
                zf.write(file_path, file_path.relative_to(source_dir.parent))


def zip_shareable_maps(map_data_dir: Path, zip_path: Path) -> None:
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in iter_shareable_map_files(map_data_dir):
            arcname = Path("map_data") / file_path.relative_to(map_data_dir)
            zf.write(file_path, arcname)


def build(*, include_non_redistributable: bool) -> None:
    version = read_version()
    remove_dist_zips(version)

    if DIST.exists():
        shutil.rmtree(DIST)

    stage_map_data(
        MAP_DATA_SRC,
        MAP_DATA_STAGE,
        include_non_redistributable=include_non_redistributable,
    )

    env = os.environ.copy()
    env["BALDRICK_MAP_DATA"] = str(MAP_DATA_STAGE.resolve())

    subprocess.check_call(["pyinstaller", "baldrick.spec"], cwd=ROOT, env=env)

    os.makedirs(DIST / "routes", exist_ok=True)
    os.makedirs(DIST / "fuel_maps", exist_ok=True)
    os.makedirs(DIST / "tmp", exist_ok=True)
    (DIST / "tmp" / ".keep").write_text("", encoding="utf-8")

    shutil.copy(ROOT / "routes" / "example_route_file.yaml", DIST / "routes" / "example_route_file.yaml")
    shutil.copy(ROOT / "fuel_maps" / "example_fuel_map.yaml", DIST / "fuel_maps" / "example_fuel_map.yaml")
    shutil.copy(ROOT / "config.yaml", DIST / "config.yaml")

    app_zip = ROOT / "dist" / f"baldrick-{version}.zip"
    maps_zip = ROOT / "dist" / f"baldrick-maps-{version}.zip"

    zip_directory(DIST, app_zip)
    zip_shareable_maps(MAP_DATA_SRC, maps_zip)

    print(f"Build complete: {DIST}")
    print(f"Application zip: {app_zip}")
    print(f"Shareable maps zip: {maps_zip}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the Baldrick distributable bundle.")
    parser.add_argument(
        "--include-non-redistributable",
        action="store_true",
        help="Include maps marked redistributable: false in the app bundle (maps zip stays shareable-only).",
    )
    args = parser.parse_args()

    try:
        build(include_non_redistributable=args.include_non_redistributable)
    except MapPackagingError as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
