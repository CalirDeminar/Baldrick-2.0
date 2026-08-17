from datetime import timedelta

import pytest

from domain.map import DCSMap, MapLayer, MapSet, PixelMapPoint
from domain.position import Position
from domain.route import Waypoint
from parsing.map_loader import load_layer_from_file, load_map_set
from shared.errors import MapError


def _grid_layer(name: str) -> MapLayer:
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
        name=name,
        pixel_map=pixel_map,
        projection_adjustment_deg=0.0,
        image_file=f"{name}.jpg",
    )


@pytest.fixture
def ambiguous_waypoint() -> Waypoint:
    return Waypoint(
        name="AMBIG",
        position=Position.new(latitude=(49, 30, 0), longitude=(11, 30, 0)),
        tags=[],
    )


@pytest.fixture
def ambiguous_map_set() -> MapSet:
    return MapSet([_grid_layer("GERMANY"), _grid_layer("NORMANDY")])


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

    def test_max_leg_length_loaded_from_yaml(self, tmp_path):
        path = tmp_path / "hd.yaml"
        path.write_text(
            "\n".join(
                [
                    "name: HD Area",
                    "image_file: HD.png",
                    "max_leg_length: 50",
                    "pixel_map:",
                    "  - { lat: '50, 0, 0', long: '08, 0, 0', x_pixel: 0, y_pixel: 0 }",
                    "  - { lat: '50, 0, 0', long: '09, 0, 0', x_pixel: 100, y_pixel: 0 }",
                    "  - { lat: '51, 0, 0', long: '08, 0, 0', x_pixel: 0, y_pixel: 100 }",
                    "  - { lat: '51, 0, 0', long: '09, 0, 0', x_pixel: 100, y_pixel: 100 }",
                ]
            ),
            encoding="utf-8",
        )
        layer = load_layer_from_file(path)
        assert layer.max_leg_length == 50

    def test_max_leg_length_defaults_unset(self, tmp_path):
        path = tmp_path / "base.yaml"
        path.write_text(
            "\n".join(
                [
                    "name: GERMANY",
                    "pixel_map:",
                    "  - { lat: '50, 0, 0', long: '08, 0, 0', x_pixel: 0, y_pixel: 0 }",
                    "  - { lat: '50, 0, 0', long: '09, 0, 0', x_pixel: 100, y_pixel: 0 }",
                    "  - { lat: '51, 0, 0', long: '08, 0, 0', x_pixel: 0, y_pixel: 100 }",
                    "  - { lat: '51, 0, 0', long: '09, 0, 0', x_pixel: 100, y_pixel: 100 }",
                ]
            ),
            encoding="utf-8",
        )
        layer = load_layer_from_file(path)
        assert layer.max_leg_length is None

    def test_germany_high_detail_max_leg_length(self):
        overlay = next(
            layer
            for layer in load_map_set().overlays
            if layer.name.lower() == "germany high detail"
        )
        assert overlay.max_leg_length == 50


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

    def test_candidate_bases_returns_all_containing_maps(
        self, ambiguous_map_set: MapSet, ambiguous_waypoint: Waypoint
    ):
        candidates = ambiguous_map_set.candidate_bases([ambiguous_waypoint])
        assert {layer.name for layer in candidates} == {"GERMANY", "NORMANDY"}

    def test_ambiguous_route_uses_chooser(
        self, ambiguous_map_set: MapSet, ambiguous_waypoint: Waypoint
    ):
        def pick_normandy(candidates: list[MapLayer]) -> MapLayer:
            return next(layer for layer in candidates if layer.name == "NORMANDY")

        selection = ambiguous_map_set.select_for(
            [ambiguous_waypoint], chooser=pick_normandy
        )
        assert selection.dcs_map == DCSMap.NORMANDY

    def test_ambiguous_route_uses_preferred_map(
        self, ambiguous_map_set: MapSet, ambiguous_waypoint: Waypoint
    ):
        selection = ambiguous_map_set.select_for(
            [ambiguous_waypoint], preferred=DCSMap.GERMANY
        )
        assert selection.dcs_map == DCSMap.GERMANY

    def test_preferred_map_not_containing_route_raises(
        self, ambiguous_map_set: MapSet
    ):
        outside = Waypoint(
            name="OCEAN",
            position=Position.new((0, 0, 0), (0, 0, 0)),
            tags=[],
        )
        with pytest.raises(MapError, match="does not fully contain"):
            ambiguous_map_set.select_for([outside], preferred=DCSMap.GERMANY)

    def test_ambiguous_route_defaults_to_first_candidate_without_chooser(
        self, ambiguous_map_set: MapSet, ambiguous_waypoint: Waypoint
    ):
        selection = ambiguous_map_set.select_for([ambiguous_waypoint])
        assert selection.dcs_map == DCSMap.GERMANY
