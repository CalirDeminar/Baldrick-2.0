from datetime import timedelta

from app.pipeline import _plan_with_turns
from domain.config import Config
from domain.position import Position
from domain.route import Route, Waypoint
from domain.turn_geometry import (
    _meters_to_route_units,
    _turn_radius_m,
    compute_turns,
    effective_leg_distances,
)
from shared.enums import Tag
from shared.units import DistanceUnit


def make_conf(**kw) -> Config:
    defaults = dict(
        min_cruise_speed=360,
        default_cruise_speed=420,
        dash_speed=540,
        units=DistanceUnit.NAUTICAL,
        turn_g=2.0,
    )
    defaults.update(kw)
    return Config(**defaults)


def wp(name, lat, lon, speed=None) -> Waypoint:
    return Waypoint(
        name=name,
        position=Position.from_decimal(lat, lon),
        speed_to=speed,
    )


def make_route(waypoints, conf) -> Route:
    return Route.from_config("R", waypoints, conf)


class TestTurnRadius:
    def test_radius_at_420kts_2g_is_about_one_and_half_nm(self):
        radius_m = _turn_radius_m(420, DistanceUnit.NAUTICAL, 2.0, None)
        radius_nm = _meters_to_route_units(radius_m, DistanceUnit.NAUTICAL)
        assert 1.3 <= radius_nm <= 1.7

    def test_rate_limit_can_dominate(self):
        r_g = _turn_radius_m(420, DistanceUnit.NAUTICAL, 2.0, None)
        r_rate = _turn_radius_m(420, DistanceUnit.NAUTICAL, 2.0, 3.0)
        assert r_rate > r_g


class TestComputeTurns:
    def test_left_turn_places_exit_toward_next_waypoint(self):
        conf = make_conf()
        route = make_route(
            [
                wp("a", 50.0, 10.0, speed=420),
                wp("b", 50.0, 10.5, speed=420),
                wp("c", 50.2, 10.5, speed=420),
            ],
            conf,
        )
        for w in route.main_waypoints:
            w.speed_to = 420
        turns = compute_turns(route, conf)
        assert turns[0] is None
        assert turns[-1] is None
        arc = turns[1]
        assert arc is not None
        assert arc.direction.value == "left"
        exit_bearing = route.main_waypoints[2].position.bearing_from(arc.exit_point)
        direct = route.main_waypoints[2].position.bearing_from(route.main_waypoints[1].position)
        assert abs((exit_bearing - direct + 180) % 360 - 180) < 15

    def test_colinear_waypoints_skip_turn(self):
        conf = make_conf()
        route = make_route(
            [
                wp("a", 50.0, 10.0, speed=420),
                wp("b", 50.0, 10.5, speed=420),
                wp("c", 50.0, 11.0, speed=420),
            ],
            conf,
        )
        for w in route.main_waypoints:
            w.speed_to = 420
        turns = compute_turns(route, conf)
        assert turns[1] is None

    def test_too_close_next_waypoint_clamps_and_sets_required_g(self):
        conf = make_conf(turn_g=2.0)
        route = make_route(
            [
                wp("a", 50.0, 10.0, speed=420),
                wp("b", 50.0, 10.01, speed=420),
                wp("c", 50.01, 10.015, speed=420),
            ],
            conf,
        )
        for w in route.main_waypoints:
            w.speed_to = 420
        turns = compute_turns(route, conf)
        arc = turns[1]
        assert arc is not None
        assert arc.required_g is not None
        assert arc.required_g > conf.turn_g


class TestMultiPassPlanning:
    def test_anchored_route_with_turns_converges(self):
        """Re-planning must not treat pass-1 computed times as hard anchors.

        Regression test: with a single TGT timestamp anchor and doglegged legs,
        the second pass previously failed with an impossible-segment ToTError
        because every waypoint had been committed a timestamp.
        """
        conf = make_conf()
        waypoints = [
            wp("start", 50.0, 8.0),
            wp("bend1", 50.4, 8.6),
            wp("bend2", 50.1, 9.2),
            wp("ip", 50.5, 9.8),
            wp("tgt", 50.3, 10.2),
        ]
        waypoints[3].tags = [Tag.IP]
        waypoints[4].tags = [Tag.TGT]
        waypoints[4].timestamp = timedelta(hours=12, minutes=35)
        route = make_route(waypoints, conf)

        warnings = _plan_with_turns(route, conf, None, None)

        assert not any("did not fully converge" in w for w in warnings)
        assert route.main_waypoints[-1].timestamp == timedelta(hours=12, minutes=35)
        assert route.turn_arcs is not None
        assert any(arc is not None for arc in route.turn_arcs)


class TestEffectiveLegDistances:
    def test_includes_arc_and_trimmed_straight(self):
        conf = make_conf()
        route = make_route(
            [
                wp("a", 50.0, 10.0, speed=420),
                wp("b", 50.0, 10.5, speed=420),
                wp("c", 50.2, 10.5, speed=420),
            ],
            conf,
        )
        for w in route.main_waypoints:
            w.speed_to = 420
        turns = compute_turns(route, conf)
        dist = effective_leg_distances(route, turns)
        straight_only = route.main_waypoints[2].position.distance_from(
            route.main_waypoints[1].position, route.units
        )
        assert dist[2] > straight_only
        if turns[1] is not None:
            assert dist[2] >= turns[1].arc_length
