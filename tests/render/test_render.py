from datetime import timedelta

import pyvips

from domain.config import Config
from domain.map import MapLayer, MapSelection, PixelMapPoint
from domain.position import Position
from domain.route import Route, Waypoint
from rendering import overlays
from rendering.geometry import compute_north_up_layout
from rendering.kneeboard import build_doghouse_lines, format_relative, render_contingency, render_leg
from shared.enums import Tag
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
