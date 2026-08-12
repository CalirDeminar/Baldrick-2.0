"""Map asset selection and staging for builds and release zips."""
from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

import yaml


class _PlainLoader(yaml.SafeLoader):
    """SafeLoader with implicit type resolution disabled."""


_PlainLoader.yaml_implicit_resolvers = {}


@dataclass(frozen=True)
class MapAsset:
    yaml_path: Path
    image_path: Path
    redistributable: bool


class MapPackagingError(Exception):
    """Raised when required map assets are missing for packaging."""


def _load_map_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.load(f, Loader=_PlainLoader)
    if not isinstance(data, dict):
        raise MapPackagingError(f"Invalid map YAML (expected mapping): {path}")
    return data


def is_redistributable(data: dict) -> bool:
    value = data.get("redistributable", True)
    if isinstance(value, str):
        return value.strip().lower() not in {"false", "no", "0"}
    return bool(value)


def resolve_image_file(data: dict) -> str:
    name = str(data["name"])
    return str(data.get("image_file") or f"{name.strip().upper()}.jpg")


def iter_map_assets(map_data_dir: Path) -> list[MapAsset]:
    assets: list[MapAsset] = []
    image_dir = map_data_dir / "image_files"
    for yaml_path in sorted(map_data_dir.glob("*.yaml")):
        data = _load_map_yaml(yaml_path)
        image_file = resolve_image_file(data)
        assets.append(
            MapAsset(
                yaml_path=yaml_path,
                image_path=image_dir / image_file,
                redistributable=is_redistributable(data),
            )
        )
    return assets


def _selected_assets(
    map_data_dir: Path,
    *,
    include_non_redistributable: bool,
) -> list[MapAsset]:
    selected: list[MapAsset] = []
    for asset in iter_map_assets(map_data_dir):
        if asset.redistributable or include_non_redistributable:
            selected.append(asset)
    return selected


def _require_images(assets: list[MapAsset], *, context: str) -> None:
    missing = [asset.image_path for asset in assets if not asset.image_path.is_file()]
    if missing:
        lines = "\n".join(f"  - {path}" for path in missing)
        raise MapPackagingError(f"Missing map image(s) for {context}:\n{lines}")


def stage_map_data(
    src_dir: Path,
    dest_dir: Path,
    *,
    include_non_redistributable: bool,
) -> list[MapAsset]:
    """Copy selected map YAML and image files into ``dest_dir`` (mirrors ``map_data/``)."""
    if dest_dir.exists():
        shutil.rmtree(dest_dir)

    assets = _selected_assets(src_dir, include_non_redistributable=include_non_redistributable)
    _require_images(assets, context="app bundle staging")

    image_dest_dir = dest_dir / "image_files"
    image_dest_dir.mkdir(parents=True, exist_ok=True)

    for asset in assets:
        shutil.copy2(asset.yaml_path, dest_dir / asset.yaml_path.name)
        shutil.copy2(asset.image_path, image_dest_dir / asset.image_path.name)

    return assets


def iter_shareable_map_files(map_data_dir: Path) -> list[Path]:
    """Return shareable map YAML and image paths rooted under ``map_data_dir``."""
    shareable = [asset for asset in iter_map_assets(map_data_dir) if asset.redistributable]
    _require_images(shareable, context="shareable maps zip")
    files: list[Path] = []
    for asset in shareable:
        files.append(asset.yaml_path)
        files.append(asset.image_path)
    return files
