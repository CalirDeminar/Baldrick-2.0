from datetime import timedelta

import pytest

from domain.map import DCSMap, MapLayer, MapSet
from domain.position import Position
from domain.route import Waypoint
from parsing.map_loader import load_map_set
from shared.errors import MapError


class TestBounds:
    def test_bounds_match_grid_extents(self, grid_layer: MapLayer):
        (min_lat, max_lat), (min_long, max_long) = grid_layer.bounds
        assert (min_lat, max_lat, min_long, max_long) == (48, 50, 10, 12)

    def test_point_within_map_accepts_interior_point(self, grid_layer: MapLayer):
        assert grid_layer.point_within_map(Position.new((49, 30, 0), (11, 30, 0)))

    def test_point_within_map_rejects_boundary(self, grid_layer: MapLayer):
        assert not grid_layer.point_within_map(Position.new((50, 0, 0), (11, 0, 0)))
        assert not grid_layer.point_within_map(Position.new((49, 0, 0), (12, 0, 0)))


class TestLoad:
    def test_load_includes_germany(self):
        names = {b.dcs_map for b in load_map_set().bases}
        assert DCSMap.GERMANY in names

    def test_germany_projection_adjustment(self, germany_layer: MapLayer):
        assert germany_layer.projection_adjustment_deg == -10

    def test_germany_pixel_map_populated(self, germany_layer: MapLayer):
        assert len(germany_layer.pixel_map) > 0


class TestNeighboringPixels:
    def test_returns_four_corners(self, grid_layer: MapLayer):
        sw, nw, se, ne = grid_layer.get_neighboring_pixels(Position.new((49, 30, 0), (10, 30, 0)))
        assert (sw.position.latitude.to_decimal(), sw.position.longitude.to_decimal()) == (49, 10)
        assert (nw.position.latitude.to_decimal(), nw.position.longitude.to_decimal()) == (50, 10)
        assert (se.position.latitude.to_decimal(), se.position.longitude.to_decimal()) == (49, 11)
        assert (ne.position.latitude.to_decimal(), ne.position.longitude.to_decimal()) == (50, 11)


class TestGetPixels:
    def test_exact_grid_point(self, grid_layer: MapLayer):
        assert grid_layer.get_pixels_for_position(Position.new((49, 0, 0), (10, 0, 0))) == (49010, 5000)

    def test_interpolates_midpoint(self, grid_layer: MapLayer):
        assert grid_layer.get_pixels_for_position(Position.new((49, 30, 0), (10, 30, 0))) == (49510, 5055)

    def test_germany_exact_grid_point(self, germany_layer: MapLayer):
        assert germany_layer.get_pixels_for_position(Position.new((55, 0, 0), (10, 0, 0))) == (20126, 5420)


class TestSelection:
    def test_selects_map_containing_route(self, germany_waypoint: Waypoint):
        selection = load_map_set().select_for([germany_waypoint])
        assert selection.dcs_map == DCSMap.GERMANY

    def test_out_of_bounds_reports_waypoints(self):
        outside = Waypoint(name="OCEAN", position=Position.new((0, 0, 0), (0, 0, 0)), tags=[])
        with pytest.raises(MapError, match="out of bounds"):
            load_map_set().select_for([outside])
