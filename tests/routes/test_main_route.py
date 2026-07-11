from domain.config import Config
from domain.position import Position
from domain.route import Route, Waypoint
from shared.enums import Tag
from shared.units import DistanceUnit


def _conf() -> Config:
    return Config(
        min_cruise_speed=300,
        default_cruise_speed=420,
        dash_speed=540,
        units=DistanceUnit.NAUTICAL,
    )


def _wp(name, lat, lon, tags=()) -> Waypoint:
    return Waypoint(
        name=name,
        position=Position.new((lat, 0, 0), (lon, 0, 0)),
        tags=list(tags),
    )


def test_main_waypoints_excludes_divert():
    route = Route.from_config(
        "R",
        [
            _wp("home", 50, 10, tags=[Tag.HOME]),
            _wp("a", 50, 11),
            _wp("divert", 50, 12, tags=[Tag.DIVERT]),
            _wp("b", 50, 13),
        ],
        _conf(),
    )
    assert [wp.name for wp in route.main_waypoints] == ["home", "a", "b"]
    assert [wp.name for wp in route.divert_waypoints] == ["divert"]


def test_is_divert_property():
    wp = _wp("divert", 50, 10, tags=[Tag.DIVERT])
    assert wp.is_divert
    assert not _wp("home", 50, 10, tags=[Tag.HOME]).is_divert


def test_leg_crosses_flot_empty():
    route = Route.from_config("R", [_wp("a", 50, 10), _wp("b", 51, 11)], _conf())
    a = Position.new((50, 0, 0), (10, 0, 0))
    b = Position.new((51, 0, 0), (11, 0, 0))
    assert not route.leg_crosses_flot(a, b)


def test_leg_crosses_flot_detects_intersection():
    flot = [
        Position.new((0, 0, 0), (10, 0, 0)),
        Position.new((10, 0, 0), (0, 0, 0)),
    ]
    route = Route.from_config(
        "R",
        [_wp("a", 0, 0), _wp("b", 10, 10)],
        _conf(),
        flot=flot,
    )
    leg_start = Position.new((0, 0, 0), (0, 0, 0))
    leg_end = Position.new((10, 0, 0), (10, 0, 0))
    assert route.leg_crosses_flot(leg_start, leg_end)


def test_leg_crosses_flot_parallel_does_not_cross():
    flot = [
        Position.new((5, 0, 0), (0, 0, 0)),
        Position.new((5, 0, 0), (10, 0, 0)),
    ]
    route = Route.from_config(
        "R",
        [_wp("a", 0, 0), _wp("b", 0, 10)],
        _conf(),
        flot=flot,
    )
    leg_start = Position.new((0, 0, 0), (0, 0, 0))
    leg_end = Position.new((0, 0, 0), (10, 0, 0))
    assert not route.leg_crosses_flot(leg_start, leg_end)
