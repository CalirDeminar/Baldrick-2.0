from datetime import timedelta
import math

import pyvips
import pytest

from domain.config import Config
from domain.map import DCSMap, MapLayer, MapSelection, PixelMapPoint
from domain.position import Position
from domain.route import Route, Waypoint
from domain.turn_geometry import compute_turns
from parsing.map_loader import load_map_set
from parsing.route_loader import load_route
from rendering import overlays
from rendering.geometry import compute_north_up_layout
from rendering.kneeboard import build_doghouse_lines, format_relative, render_contingency, render_leg
from shared.enums import Tag
from shared.paths import routes_dir
from shared.units import DistanceUnit


def _conf() -> Config:
    return Config(min_cruise_speed=300, default_cruise_speed=420, dash_speed=540,
                  units=DistanceUnit.NAUTICAL)


def _selection() -> MapSelection:
    pos = Position.new((50, 0, 0), (10, 0, 0))
    base = MapLayer(
        name="GERMANY",
        pixel_map={pos: PixelMapPoint(position=pos, x_pixel=0, y_pixel=0)},
        image_file="GERMANY.jpg",
        mag_var=2.0,
    )
    return MapSelection(base=base, overlays=[])


def test_render_leg_outputs_fixed_size():
    conf = _conf()
    base_image = (pyvips.Image.black(3000, 3000, bands=3) + [80, 120, 60]).cast("uchar")
    route = Route.from_config(
        "R",
        [
            Waypoint(name="a", position=Position.new((50, 0, 0), (10, 0, 0)),
                     timestamp=timedelta(hours=12), speed_to=420),
            Waypoint(name="tgt", position=Position.new((50, 10, 0), (10, 10, 0)),
                     tags=[Tag.TGT], timestamp=timedelta(hours=12, minutes=5), speed_to=540),
        ],
        conf,
    )
    base_pixels = [(1000, 1200), (2000, 1800)]
    board = render_leg(base_image, _selection(), route, 1, conf, base_pixels)
    assert board.size == (1600, 2400)
    assert board.mode == "RGB"


def test_render_leg_omits_overlays_above_max_leg_length(monkeypatch):
    conf = _conf()
    base_image = (pyvips.Image.black(3000, 3000, bands=3) + [80, 120, 60]).cast("uchar")
    route = Route.from_config(
        "R",
        [
            Waypoint(name="a", position=Position.new((50, 0, 0), (10, 0, 0)),
                     timestamp=timedelta(hours=12), speed_to=420),
            Waypoint(name="tgt", position=Position.new((50, 10, 0), (10, 10, 0)),
                     tags=[Tag.TGT], timestamp=timedelta(hours=12, minutes=5), speed_to=540),
        ],
        conf,
    )
    pos = Position.new((50, 0, 0), (10, 0, 0))
    pixel = PixelMapPoint(position=pos, x_pixel=0, y_pixel=0)
    base = MapLayer(name="GERMANY", pixel_map={pos: pixel}, image_file="GERMANY.jpg")
    hd = MapLayer(
        name="HD",
        pixel_map={pos: pixel},
        image_file="HD.jpg",
        max_leg_length=1,
    )
    always = MapLayer(name="ALWAYS", pixel_map={pos: pixel}, image_file="ALWAYS.jpg")
    captured = {}

    def fake_composite(canvas, layout, selection):
        captured["names"] = [overlay.name for overlay in selection.overlays]
        return canvas

    monkeypatch.setattr("rendering.kneeboard.composite_overlays", fake_composite)
    render_leg(
        base_image,
        MapSelection(base=base, overlays=[hd, always]),
        route,
        1,
        conf,
        [(1000, 1200), (2000, 1800)],
    )
    assert captured["names"] == ["ALWAYS"]


def test_render_overview_omits_overlays_with_max_leg_length(monkeypatch):
    from rendering.cards import render_overview

    conf = _conf()
    base_image = (pyvips.Image.black(3000, 3000, bands=3) + [80, 120, 60]).cast("uchar")
    route = Route.from_config(
        "R",
        [
            Waypoint(name="a", position=Position.new((50, 0, 0), (10, 0, 0)),
                     timestamp=timedelta(hours=12), speed_to=420),
            Waypoint(name="tgt", position=Position.new((50, 10, 0), (10, 10, 0)),
                     tags=[Tag.TGT], timestamp=timedelta(hours=12, minutes=5), speed_to=540),
        ],
        conf,
    )
    pos = Position.new((50, 0, 0), (10, 0, 0))
    pixel = PixelMapPoint(position=pos, x_pixel=0, y_pixel=0)
    base = MapLayer(name="GERMANY", pixel_map={pos: pixel}, image_file="GERMANY.jpg")
    hd = MapLayer(
        name="HD",
        pixel_map={pos: pixel},
        image_file="HD.jpg",
        max_leg_length=10_000,
    )
    always = MapLayer(name="ALWAYS", pixel_map={pos: pixel}, image_file="ALWAYS.jpg")
    captured = {}

    def fake_composite(canvas, layout, selection):
        captured["names"] = [overlay.name for overlay in selection.overlays]
        return canvas

    monkeypatch.setattr("rendering.cards.composite_overlays", fake_composite)
    render_overview(
        base_image,
        MapSelection(base=base, overlays=[hd, always]),
        route,
        conf,
        [(1000, 1200), (2000, 1800)],
        None,
    )
    assert captured["names"] == ["ALWAYS"]


def test_format_relative_to_push():
    assert format_relative(12.5, 12.0) == "+00:30:00"
    assert format_relative(11.75, 12.0) == "-00:15:00"


def test_render_contingency_outputs_fixed_size():
    conf = _conf()
    base_image = (pyvips.Image.black(3000, 3000, bands=3) + [80, 120, 60]).cast("uchar")
    divert = Waypoint(
        name="Spangdahlem",
        position=Position.new((50, 0, 0), (10, 5, 0)),
        tags=[Tag.DIVERT],
        notes="Via valley\\nChannel 5",
    )
    route = Route.from_config(
        "R",
        [
            Waypoint(name="a", position=Position.new((50, 0, 0), (10, 0, 0)),
                     timestamp=timedelta(hours=12), speed_to=420),
            Waypoint(name="tgt", position=Position.new((50, 10, 0), (10, 10, 0)),
                     tags=[Tag.TGT], timestamp=timedelta(hours=12, minutes=5), speed_to=540),
            divert,
        ],
        conf,
    )
    base_pixels = [(1000, 1200), (2000, 1800), (1500, 1500)]
    board = render_contingency(base_image, _selection(), route, divert, base_pixels)
    assert board.size == (1600, 2400)
    assert board.mode == "RGB"


def test_contingency_layout_is_north_up():
    layout = compute_north_up_layout((1500, 1500), 3000, 3000)
    assert layout.angle_deg == 0.0


def test_build_doghouse_lines_applies_projection_adjustment():
    conf = _conf()
    pos = Position.new((50, 0, 0), (10, 0, 0))
    base = MapLayer(
        name="GERMANY",
        pixel_map={pos: PixelMapPoint(position=pos, x_pixel=0, y_pixel=0)},
        image_file="GERMANY.jpg",
        projection_adjustment_deg=-10,
        mag_var=0.0,
    )
    route = Route.from_config(
        "R",
        [
            Waypoint(name="a", position=Position.new((50, 0, 0), (10, 0, 0)),
                     timestamp=timedelta(hours=12), speed_to=420),
            Waypoint(name="b", position=Position.new((51, 0, 0), (10, 0, 0)),
                     timestamp=timedelta(hours=12, minutes=5), speed_to=420),
        ],
        conf,
    )
    lines = build_doghouse_lines(route, 1, MapSelection(base=base, overlays=[]), conf)
    mc = next(row[1][0] for row in lines if row[0] == "MC:")
    true_course = route.main_waypoints[1].position.bearing_from(
        route.main_waypoints[0].position
    )
    expected = int(round((true_course - 10) % 360))
    assert mc == f"{expected}\u00b0"


def test_build_doghouse_lines_applies_route_magvar():
    conf = _conf()
    pos = Position.new((50, 0, 0), (10, 0, 0))
    base = MapLayer(
        name="GERMANY",
        pixel_map={pos: PixelMapPoint(position=pos, x_pixel=0, y_pixel=0)},
        image_file="GERMANY.jpg",
        projection_adjustment_deg=-10,
        mag_var=2.0,
    )
    route = Route.from_config(
        "R",
        [
            Waypoint(name="a", position=Position.new((50, 0, 0), (10, 0, 0)),
                     timestamp=timedelta(hours=12), speed_to=420),
            Waypoint(name="b", position=Position.new((51, 0, 0), (10, 0, 0)),
                     timestamp=timedelta(hours=12, minutes=5), speed_to=420),
            Waypoint(name="c", position=Position.new((51, 0, 0), (11, 0, 0)),
                     timestamp=timedelta(hours=12, minutes=10), speed_to=420),
        ],
        conf,
        magvar=-13,
    )
    lines = build_doghouse_lines(route, 1, MapSelection(base=base, overlays=[]), conf)
    mc = next(row[1][0] for row in lines if row[0] == "MC:")
    nmc = next(row[1][0] for row in lines if row[0] == "NMC:")
    true_course = route.main_waypoints[1].position.bearing_from(
        route.main_waypoints[0].position
    )
    next_true = route.main_waypoints[2].position.bearing_from(
        route.main_waypoints[1].position
    )
    expected_mc = int(round((true_course - 10 - (-13)) % 360))
    expected_nmc = int(round((next_true - 10 - (-13)) % 360))
    assert mc == f"{expected_mc}\u00b0"
    assert nmc == f"{expected_nmc}\u00b0"


def test_build_doghouse_lines_uses_turn_exit_heading_not_point_to_point():
    conf = _conf()
    pos = Position.new((50, 0, 0), (10, 0, 0))
    projection = -10
    magvar = -13
    base = MapLayer(
        name="GERMANY",
        pixel_map={pos: PixelMapPoint(position=pos, x_pixel=0, y_pixel=0)},
        image_file="GERMANY.jpg",
        projection_adjustment_deg=projection,
        mag_var=2.0,
    )
    route = Route.from_config(
        "R",
        [
            Waypoint(name="a", position=Position.from_decimal(50.0, 10.0),
                     timestamp=timedelta(hours=12), speed_to=420),
            Waypoint(name="b", position=Position.from_decimal(50.0, 10.5),
                     timestamp=timedelta(hours=12, minutes=5), speed_to=420),
            Waypoint(name="c", position=Position.from_decimal(50.2, 10.5),
                     timestamp=timedelta(hours=12, minutes=10), speed_to=420),
        ],
        conf,
        magvar=magvar,
    )
    route.turn_arcs = compute_turns(route, conf)
    arc = route.turn_arcs[1]
    assert arc is not None

    dest = route.main_waypoints[2].position
    from_exit = dest.bearing_from(arc.exit_point)
    from_wp = dest.bearing_from(route.main_waypoints[1].position)
    expected = int(round((from_exit + projection - magvar) % 360))
    point_to_point = int(round((from_wp + projection - magvar) % 360))
    assert expected != point_to_point

    nmc = next(
        row[1][0]
        for row in build_doghouse_lines(route, 1, MapSelection(base=base, overlays=[]), conf)
        if row[0] == "NMC:"
    )
    mc = next(
        row[1][0]
        for row in build_doghouse_lines(route, 2, MapSelection(base=base, overlays=[]), conf)
        if row[0] == "MC:"
    )
    assert nmc == f"{expected}\u00b0"
    assert mc == f"{expected}\u00b0"


def _doghouse_value(lines, label: str) -> str:
    return next(row[1][0] for row in lines if row[0] == label)


def test_germany_test_route_cardinal_headings_use_clockwise_projection():
    """The Germany test route is a lat/long box: N, E, S, W, then NE.

    Geographic due-north is 000 true, but the DCS Germany map is ~10° clockwise,
    so MC must be 010 — not 350 (the previous wrong-sign offset).
    """
    conf = _conf()
    route = load_route(routes_dir() / "germany_test_route.yaml", conf)
    germany = next(layer for layer in load_map_set().bases if layer.dcs_map == DCSMap.GERMANY)
    assert germany.projection_adjustment_deg == 10
    selection = MapSelection(base=germany, overlays=[])
    main = route.main_waypoints

    true_north = main[1].position.bearing_from(main[0].position)
    assert true_north == pytest.approx(0.0, abs=0.01)
    assert _doghouse_value(build_doghouse_lines(route, 1, selection, conf), "MC:") == "10\u00b0"

    p0 = germany.get_pixels_for_position(main[0].position)
    p1 = germany.get_pixels_for_position(main[1].position)
    pixel_heading = (math.degrees(math.atan2(p1[0] - p0[0], -(p1[1] - p0[1]))) + 360) % 360
    assert pixel_heading == pytest.approx(10.0, abs=1.0)

    # Point-to-point (no turn arcs): remaining cardinals and the closing diagonal.
    expected_mc = {2: "100\u00b0", 3: "190\u00b0", 4: "280\u00b0", 5: "42\u00b0"}
    for index, heading in expected_mc.items():
        assert _doghouse_value(
            build_doghouse_lines(route, index, selection, conf), "MC:"
        ) == heading


def test_build_doghouse_lines_includes_flot_warning():
    conf = _conf()
    flot = [
        Position.new((5, 0, 0), (0, 0, 0)),
        Position.new((5, 0, 0), (20, 0, 0)),
    ]
    route = Route.from_config(
        "R",
        [
            Waypoint(name="a", position=Position.new((0, 0, 0), (0, 0, 0)),
                     timestamp=timedelta(hours=12), speed_to=420),
            Waypoint(name="b", position=Position.new((10, 0, 0), (10, 0, 0)),
                     timestamp=timedelta(hours=12, minutes=5), speed_to=420),
        ],
        conf,
        flot=flot,
    )
    lines = build_doghouse_lines(route, 1, _selection(), conf)
    warning_rows = [
        row for row in lines if row[1] == ["! FLOT CROSSED THIS LEG"]
    ]
    assert len(warning_rows) == 1
    assert warning_rows[0][2] == overlays.FLOT_COLOUR


def test_render_leg_with_flot_outputs_fixed_size():
    conf = _conf()
    base_image = (pyvips.Image.black(3000, 3000, bands=3) + [80, 120, 60]).cast("uchar")
    flot = [
        Position.new((5, 0, 0), (0, 0, 0)),
        Position.new((5, 0, 0), (20, 0, 0)),
    ]
    route = Route.from_config(
        "R",
        [
            Waypoint(name="a", position=Position.new((0, 0, 0), (0, 0, 0)),
                     timestamp=timedelta(hours=12), speed_to=420),
            Waypoint(name="b", position=Position.new((10, 0, 0), (10, 0, 0)),
                     timestamp=timedelta(hours=12, minutes=5), speed_to=420),
        ],
        conf,
        flot=flot,
    )
    base_pixels = [(1000, 1200), (2000, 1800)]
    flot_pixels = [(1200, 1500), (1800, 1500)]
    board = render_leg(
        base_image, _selection(), route, 1, conf, base_pixels, flot_pixels
    )
    assert board.size == (1600, 2400)
    assert board.mode == "RGB"
