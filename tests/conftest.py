from datetime import timedelta

import pytest

from routes.map import DCSMap, MapLayer, PixelMapPoint
from routes.position import Position
from routes.route import Waypoint


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
    from routes.map import MapSet

    return next(b for b in MapSet.load().bases if b.dcs_map == DCSMap.GERMANY)


@pytest.fixture
def germany_waypoint() -> Waypoint:
    return Waypoint(
        name="TEST",
        position=Position.new(latitude=(50, 0, 0), longitude=(11, 0, 0)),
        speed_to=300,
        tags=[],
    )
