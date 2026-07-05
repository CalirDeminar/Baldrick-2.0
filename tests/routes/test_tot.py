from datetime import timedelta

import pytest

from config.config import Config, DistanceUnit
from enums import Tag
from errors import ToTError
from routes.position import Position
from routes.route import Route, Waypoint
from routes.tot import plan_route_times


def make_conf(**kw) -> Config:
    defaults = dict(
        min_cruise_speed=360,
        default_cruise_speed=420,
        dash_speed=540,
        units=DistanceUnit.NAUTICAL,
    )
    defaults.update(kw)
    return Config(**defaults)


def wp(name, lat, lon, tags=(), timestamp=None, speed=None) -> Waypoint:
    return Waypoint(
        name=name,
        position=Position.new((lat, 0, 0), (lon, 0, 0)),
        tags=list(tags),
        timestamp=timestamp,
        speed_to=speed,
    )


def make_route(waypoints, conf) -> Route:
    return Route.from_config("R", waypoints, conf)


class TestUnanchored:
    def test_uses_default_cruise_and_dash(self):
        conf = make_conf()
        route = make_route(
            [
                wp("start", 50, 10),
                wp("ip", 50, 11, tags=[Tag.IP]),
                wp("tgt", 50, 12, tags=[Tag.TGT]),
            ],
            conf,
        )
        warnings = plan_route_times(route, conf)
        assert any("default cruise" in w for w in warnings)
        assert route.waypoints[1].speed_to == 420
        assert route.waypoints[2].speed_to == 540  # dash into target
        assert route.waypoints[0].timestamp < route.waypoints[2].timestamp


class TestAnchoredSegment:
    def test_push_to_tgt_prefers_multiple_of_60_and_hits_tot(self):
        conf = make_conf()
        route = make_route(
            [
                wp("push", 50, 10, tags=[Tag.PUSH]),
                wp("a", 50, 11),
                wp("ip", 50, 12, tags=[Tag.IP]),
                wp("tgt", 50, 13, tags=[Tag.TGT]),
            ],
            conf,
        )
        tot = timedelta(hours=12, minutes=30)
        push = timedelta(hours=12)
        warnings = plan_route_times(route, conf, time_on_target=tot, push_time=push)
        assert warnings == []
        # Cruise legs keep a multiple-of-60 speed.
        assert route.waypoints[1].speed_to % 60 == 0
        assert route.waypoints[2].speed_to % 60 == 0
        # Dash into the target.
        assert route.waypoints[3].speed_to == 540
        # Anchors are hit exactly.
        assert route.waypoints[0].timestamp == push
        assert route.waypoints[3].timestamp == tot

    def test_impossible_segment_raises(self):
        conf = make_conf()
        route = make_route(
            [
                wp("push", 50, 10, tags=[Tag.PUSH]),
                wp("ip", 50, 12, tags=[Tag.IP]),
                wp("tgt", 51, 15, tags=[Tag.TGT]),
            ],
            conf,
        )
        with pytest.raises(ToTError):
            plan_route_times(
                route,
                conf,
                time_on_target=timedelta(hours=12, seconds=1),
                push_time=timedelta(hours=12),
            )


class TestAnchorValidation:
    def test_duplicate_tot_raises(self):
        conf = make_conf()
        route = make_route(
            [
                wp("a", 50, 10, timestamp=timedelta(hours=12)),
                wp("b", 50, 11, timestamp=timedelta(hours=12)),
                wp("c", 50, 12),
            ],
            conf,
        )
        with pytest.raises(ToTError, match="same time-on-target"):
            plan_route_times(route, conf)
