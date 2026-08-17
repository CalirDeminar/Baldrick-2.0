from datetime import timedelta

import pytest

from domain.map import DCSMap, MapLayer, PixelMapPoint
from domain.position import Position
from domain.route import Waypoint
from rendering.vips_util import clear_image_cache, configure_tmpdir
from shared import paths


@pytest.fixture(autouse=True)
def isolate_app_tmp(tmp_path, monkeypatch):
    """Keep libvips scratch and map caches inside the test temp dir."""
    monkeypatch.setattr(paths, "tmp_dir", lambda: tmp_path / "app-tmp")
    configure_tmpdir()
    clear_image_cache()
    yield
    clear_image_cache()


@pytest.fixture
def grid_layer() -> MapLayer:
    """Minimal 3x3 degree grid base map with predictable pixel coordinates."""
    pixel_map: dict[Position, PixelMapPoint] = {}
    for lat in (48, 49, 50):
        for lon in (10, 11, 12):
            pos = Position.new(latitude=(lat, 0, 0), longitude=(lon, 0, 0))
            pixel_map[pos] = PixelMapPoint(
                position=pos,
                x_pixel=lat * 1000 + lon,
                y_pixel=lat * 100 + lon * 10,
            )
    return MapLayer(
        name="GERMANY",
        pixel_map=pixel_map,
        projection_adjustment_deg=0.0,
        image_file="GERMANY.jpg",
    )


@pytest.fixture
def germany_layer() -> MapLayer:
    from parsing.map_loader import load_map_set

    return next(b for b in load_map_set().bases if b.dcs_map == DCSMap.GERMANY)


@pytest.fixture
def germany_waypoint() -> Waypoint:
    return Waypoint(
        name="TEST",
        position=Position.new(latitude=(50, 0, 0), longitude=(11, 0, 0)),
        speed_to=300,
        tags=[],
    )
