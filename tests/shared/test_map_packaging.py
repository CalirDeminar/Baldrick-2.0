from __future__ import annotations

from pathlib import Path

import pytest

from shared.map_packaging import (
    MapPackagingError,
    is_redistributable,
    iter_map_assets,
    iter_shareable_map_files,
    stage_map_data,
)


def _write_map(
    map_data_dir: Path,
    *,
    stem: str,
    name: str,
    redistributable: bool | None = None,
) -> None:
    image_dir = map_data_dir / "image_files"
    image_dir.mkdir(parents=True, exist_ok=True)
    yaml_path = map_data_dir / f"{stem}.yaml"
    image_name = f"{stem.upper()}.jpg"
    image_path = image_dir / image_name

    lines = [
        f"name: {name}",
        f"image_file: {image_name}",
        "pixel_map:",
        '  - { lat: "50, 0, 0", long: "10, 0, 0", x_pixel: 0, y_pixel: 0 }',
    ]
    if redistributable is not None:
        lines.insert(2, f"redistributable: {'true' if redistributable else 'false'}")
    yaml_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    image_path.write_bytes(b"fake-image")


def test_is_redistributable_defaults_true() -> None:
    assert is_redistributable({"name": "Germany"}) is True


def test_is_redistributable_false() -> None:
    assert is_redistributable({"name": "Germany High Detail", "redistributable": False}) is False


def test_shareable_staging_excludes_non_redistributable(tmp_path: Path) -> None:
    src = tmp_path / "map_data"
    dest = tmp_path / "staged"
    _write_map(src, stem="germany", name="GERMANY")
    _write_map(src, stem="germany_high_detail", name="Germany High Detail", redistributable=False)

    staged = stage_map_data(src, dest, include_non_redistributable=False)

    assert {asset.yaml_path.name for asset in staged} == {"germany.yaml"}
    assert not (dest / "germany_high_detail.yaml").exists()
    assert (dest / "image_files" / "GERMANY.jpg").is_file()
    assert not (dest / "image_files" / "GERMANY_HIGH_DETAIL.jpg").exists()


def test_include_non_redistributable_staging_includes_restricted(tmp_path: Path) -> None:
    src = tmp_path / "map_data"
    dest = tmp_path / "staged"
    _write_map(src, stem="germany", name="GERMANY")
    _write_map(src, stem="germany_high_detail", name="Germany High Detail", redistributable=False)

    staged = stage_map_data(src, dest, include_non_redistributable=True)

    assert {asset.yaml_path.name for asset in staged} == {"germany.yaml", "germany_high_detail.yaml"}
    assert (dest / "image_files" / "GERMANY_HIGH_DETAIL.jpg").is_file()


def test_iter_shareable_map_files_only_shareable(tmp_path: Path) -> None:
    src = tmp_path / "map_data"
    _write_map(src, stem="germany", name="GERMANY")
    _write_map(src, stem="germany_high_detail", name="Germany High Detail", redistributable=False)

    files = iter_shareable_map_files(src)

    assert src / "germany.yaml" in files
    assert src / "image_files" / "GERMANY.jpg" in files
    assert src / "germany_high_detail.yaml" not in files
    assert src / "image_files" / "GERMANY_HIGH_DETAIL.jpg" not in files


def test_missing_shareable_image_raises(tmp_path: Path) -> None:
    src = tmp_path / "map_data"
    image_dir = src / "image_files"
    image_dir.mkdir(parents=True)
    (src / "germany.yaml").write_text(
        'name: GERMANY\npixel_map:\n  - { lat: "50, 0, 0", long: "10, 0, 0", x_pixel: 0, y_pixel: 0 }\n',
        encoding="utf-8",
    )

    with pytest.raises(MapPackagingError, match="Missing map image"):
        iter_shareable_map_files(src)
