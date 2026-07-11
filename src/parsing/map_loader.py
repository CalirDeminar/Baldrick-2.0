from __future__ import annotations

from pathlib import Path

import yaml

from domain.map import MapLayer, MapSet, MinAltMap, PixelMapPoint
from domain.position import Position
from shared import paths


class _PlainLoader(yaml.SafeLoader):
    """SafeLoader with implicit type resolution disabled.

    Map pixel coordinates are often written with leading zeros for alignment
    (e.g. ``05420``); the default YAML loader would interpret those as octal.
    Loading every scalar as a string and converting explicitly avoids that.
    """


_PlainLoader.yaml_implicit_resolvers = {}


def _parse_dms_triplet(value: str) -> tuple[float, float, float]:
    parts = [p.strip() for p in str(value).split(",")]
    return float(parts[0]), float(parts[1]), float(parts[2])


def _bucket_30(minutes: float) -> int:
    return 0 if minutes < 30 else 30


def min_alt_map_from_rows(rows: list[dict]) -> MinAltMap:
    cells: dict[tuple[int, int, int, int], int] = {}
    for row in rows:
        lat_d, lat_m, _ = _parse_dms_triplet(row["lat"])
        lon_d, lon_m, _ = _parse_dms_triplet(row["long"])
        key = (int(lat_d), _bucket_30(lat_m), int(lon_d), _bucket_30(lon_m))
        cells[key] = int(row["altitude_ft"])
    return MinAltMap(cells=cells)


def load_layer_from_file(path: Path) -> MapLayer:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.load(f, Loader=_PlainLoader)
    pixels: dict[Position, PixelMapPoint] = {}
    for point in data.get("pixel_map", []):
        pos = Position.new(
            latitude=_parse_dms_triplet(point["lat"]),
            longitude=_parse_dms_triplet(point["long"]),
        )
        pixels[pos] = PixelMapPoint(
            position=pos,
            x_pixel=int(point["x_pixel"]),
            y_pixel=int(point["y_pixel"]),
        )
    name = str(data["name"])
    image_file = data.get("image_file") or f"{name.strip().upper()}.jpg"
    min_alt = None
    if data.get("min_altitude_map"):
        min_alt = min_alt_map_from_rows(data["min_altitude_map"])
    return MapLayer(
        name=name,
        pixel_map=pixels,
        projection_adjustment_deg=float(data.get("projection_adjustment_deg", 0.0)),
        mag_var=float(data.get("mag_var", 0.0)),
        layer_priority=int(data.get("layer_priority", 0)),
        image_file=image_file,
        min_alt=min_alt,
    )


def load_map_set(map_data_dir: Path | None = None) -> MapSet:
    map_data_dir = map_data_dir or paths.map_data_dir()
    layers: list[MapLayer] = []
    for file in sorted(map_data_dir.iterdir()):
        if file.suffix.lower() != ".yaml":
            continue
        layers.append(load_layer_from_file(file))
    return MapSet(layers)
