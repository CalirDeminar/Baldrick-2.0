from datetime import timedelta

import pytest

from routes.map import DCSMap, MapData
from routes.position import Position
from routes.route import Waypoint


class TestMapDataBounds:
    def test_bounds_match_grid_extents(self, grid_map: MapData):
        ((min_lat, max_lat), (min_long, max_long)) = grid_map.bounds

        assert min_lat == 48
        assert max_lat == 50
        assert min_long == 10
        assert max_long == 12

    def test_point_within_map_accepts_interior_point(self, grid_map: MapData):
        position = Position.new(latitude=(49, 30, 0), longitude=(11, 30, 0))

        assert grid_map.point_within_map(position)

    def test_point_within_map_rejects_northern_boundary(self, grid_map: MapData):
        position = Position.new(latitude=(50, 0, 0), longitude=(11, 0, 0))

        assert not grid_map.point_within_map(position)

    def test_point_within_map_rejects_eastern_boundary(self, grid_map: MapData):
        position = Position.new(latitude=(49, 0, 0), longitude=(12, 0, 0))

        assert not grid_map.point_within_map(position)


class TestMapDataLoad:
    def test_load_map_set_includes_germany(self):
        maps = MapData.load_map_set()
        names = {m.name for m in maps}

        assert DCSMap.GERMANY in names

    def test_germany_map_has_expected_projection_adjustment(self, germany_map: MapData):
        assert germany_map.projection_adjustment_deg == -10

    def test_germany_map_pixel_map_is_populated(self, germany_map: MapData):
        assert len(germany_map.pixel_map) > 0


class TestGetNeighboringPixels:
    def test_returns_four_corners_of_bounding_cell(self, grid_map: MapData):
        position = Position.new(latitude=(49, 30, 0), longitude=(10, 30, 0))
        sw, nw, se, ne = grid_map.get_neighboring_pixels(position)

        assert (sw.position.latitude.to_decimal(), sw.position.longitude.to_decimal()) == (49, 10)
        assert (nw.position.latitude.to_decimal(), nw.position.longitude.to_decimal()) == (50, 10)
        assert (se.position.latitude.to_decimal(), se.position.longitude.to_decimal()) == (49, 11)
        assert (ne.position.latitude.to_decimal(), ne.position.longitude.to_decimal()) == (50, 11)


class TestGetPixelsForPosition:
    def test_returns_exact_pixel_for_grid_point(self, grid_map: MapData):
        position = Position.new(latitude=(49, 0, 0), longitude=(10, 0, 0))

        assert grid_map.get_pixels_for_position(position) == (49010, 5000)

    def test_interpolates_midpoint_between_four_corners(self, grid_map: MapData):
        position = Position.new(latitude=(49, 30, 0), longitude=(10, 30, 0))

        assert grid_map.get_pixels_for_position(position) == (49510, 5055)

    def test_interpolates_point_on_latitude_grid_line(self, grid_map: MapData):
        position = Position.new(latitude=(49, 0, 0), longitude=(10, 30, 0))

        assert grid_map.get_pixels_for_position(position) == (49010, 5005)

    def test_interpolates_point_on_longitude_grid_line(self, grid_map: MapData):
        position = Position.new(latitude=(49, 30, 0), longitude=(10, 0, 0))

        assert grid_map.get_pixels_for_position(position) == (49510, 5050)

    def test_germany_midpoint_matches_expected_values(self, germany_map: MapData):
        position = Position.new(latitude=(55, 30, 0), longitude=(10, 30, 0))

        assert germany_map.get_pixels_for_position(position) == (21378, 2254)

    def test_germany_exact_grid_point(self, germany_map: MapData):
        position = Position.new(latitude=(55, 0, 0), longitude=(10, 0, 0))

        assert germany_map.get_pixels_for_position(position) == (20126, 2832)


class TestGetMapForWaypoints:
    def test_returns_map_containing_waypoints(self, germany_waypoint: Waypoint):
        selected = MapData.get_map_for_waypoints([germany_waypoint])

        assert selected.name == DCSMap.GERMANY

    def test_raises_when_no_map_contains_route(self):
        outside = Waypoint(
            name="OCEAN",
            timestamp=timedelta(),
            position=Position.new(latitude=(0, 0, 0), longitude=(0, 0, 0)),
            speed_to=300,
            minimum_leg_alt=None,
            planned_fuel=None,
            tags=[],
        )

        with pytest.raises(ValueError, match="Route is not fully contained within any supported map"):
            MapData.get_map_for_waypoints([outside])
