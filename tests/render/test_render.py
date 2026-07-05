import pyvips

from config.config import Config, DistanceUnit
from enums import Tag
from routes.map import MapLayer, MapSelection, PixelMapPoint
from routes.position import Position
from routes.render.kneeboard import format_relative, render_leg
from routes.route import Route, Waypoint
from datetime import timedelta


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


def test_format_relative_to_push():
    assert format_relative(12.5, 12.0) == "+00:30:00"
    assert format_relative(11.75, 12.0) == "-00:15:00"
