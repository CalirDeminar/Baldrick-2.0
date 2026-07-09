import pytest

from config.config import Config, DistanceUnit
from enums import Tag
from errors import FuelError
from fuel.fuel import compute_fuel
from fuel.fuel_map import FuelMap
from routes.position import Position
from routes.route import Route, Waypoint


def make_fuel_map(capacity=16800) -> FuelMap:
    rows = [
        {"altitude_ft": 0, "speed_kts": 300, "lb_per_nm": 30.0},
        {"altitude_ft": 0, "speed_kts": 600, "lb_per_nm": 40.0},
        {"altitude_ft": 10000, "speed_kts": 300, "lb_per_nm": 20.0},
        {"altitude_ft": 10000, "speed_kts": 600, "lb_per_nm": 30.0},
    ]
    data = {"name": "TESTMAP", "capacity": capacity, "fuelMap": rows}
    # Reuse FuelMap.from_file logic via a small shim.
    from fuel.fuel_map import FuelMapBySpeed, FuelMapCell

    by_alt: dict[int, FuelMapBySpeed] = {}
    for r in rows:
        a = r["altitude_ft"]
        by_alt.setdefault(a, FuelMapBySpeed(altitude=a, map_by_speed={}))
        by_alt[a].map_by_speed[r["speed_kts"]] = FuelMapCell(
            speed_kts=r["speed_kts"], altitude_ft=a, fuel_lbs_per_nm=r["lb_per_nm"]
        )
    return FuelMap(name="TESTMAP", capacity=capacity, fuel_map_by_altitude=by_alt)


class TestInterpolation:
    def test_centre_is_average_of_corners(self):
        fm = make_fuel_map()
        assert fm.get_lb_per_mile_for_profile(5000, 450) == pytest.approx(30.0)

    def test_out_of_bounds_is_clamped(self):
        fm = make_fuel_map()
        assert not fm.is_within_bounds(20000, 700)
        assert fm.get_lb_per_mile_for_profile(20000, 700) == pytest.approx(30.0)


def make_conf(fm, **kw) -> Config:
    defaults = dict(
        min_cruise_speed=300,
        default_cruise_speed=420,
        dash_speed=540,
        units=DistanceUnit.NAUTICAL,
        reserve_fuel=2000,
        takeoff_fuel=1000,
        rtb_altitude=10000,
        rtb_speed=420,
    )
    defaults.update(kw)
    conf = Config(**defaults)
    conf.active_fuel_map = fm
    return conf


def wp(name, lat, lon, tags=(), alt=0, speed=420):
    return Waypoint(
        name=name, position=Position.new((lat, 0, 0), (lon, 0, 0)),
        tags=list(tags), altitude=alt, speed_to=speed,
    )


class TestComputeFuel:
    def _route(self, conf):
        return Route.from_config(
            "R",
            [
                wp("home", 50, 10, tags=[Tag.HOME]),
                wp("a", 50, 11),
                wp("tgt", 50, 12, tags=[Tag.TGT]),
                wp("home2", 50, 10, tags=[Tag.HOME]),
            ],
            conf,
        )

    def test_reports_bingo_and_min_fuel(self):
        fm = make_fuel_map()
        conf = make_conf(fm)
        route = self._route(conf)
        report = compute_fuel(route, conf)
        assert report.bingo_fuel is not None
        assert report.total_required > 0
        assert route.waypoints[-1].min_fuel == conf.reserve_fuel

    def test_insufficient_capacity_raises(self):
        fm = make_fuel_map(capacity=100)
        conf = make_conf(fm)
        route = self._route(conf)
        with pytest.raises(FuelError, match="cannot be flown"):
            compute_fuel(route, conf)

    def test_out_of_bounds_regime_warns(self):
        fm = make_fuel_map()
        conf = make_conf(fm)
        route = Route.from_config(
            "R",
            [
                wp("home", 50, 10, tags=[Tag.HOME]),
                wp("fast", 50, 11, speed=900, alt=0),
                wp("tgt", 50, 12, tags=[Tag.TGT]),
                wp("home2", 50, 10, tags=[Tag.HOME]),
            ],
            conf,
        )
        report = compute_fuel(route, conf)
        assert any("outside the fuel map" in w for w in report.warnings)


class TestDivertExclusion:
    def test_min_fuel_excludes_divert_leg(self):
        fm = make_fuel_map()
        conf = make_conf(fm)
        route_with_divert = Route.from_config(
            "R",
            [
                wp("home", 50, 10, tags=[Tag.HOME]),
                wp("a", 50, 11),
                wp("divert", 50, 20, tags=[Tag.DIVERT]),
                wp("b", 50, 12),
                wp("home2", 50, 10, tags=[Tag.HOME]),
            ],
            conf,
        )
        route_without = Route.from_config(
            "R",
            [
                wp("home", 50, 10, tags=[Tag.HOME]),
                wp("a", 50, 11),
                wp("b", 50, 12),
                wp("home2", 50, 10, tags=[Tag.HOME]),
            ],
            conf,
        )
        report_with = compute_fuel(route_with_divert, conf)
        report_without = compute_fuel(route_without, conf)
        assert report_with.total_required == report_without.total_required
        assert route_with_divert.main_waypoints[-1].min_fuel == conf.reserve_fuel
        assert route_with_divert.divert_waypoints[0].min_fuel is None

    def test_bingo_uses_nearer_divert(self):
        fm = make_fuel_map()
        conf = make_conf(fm)
        route = Route.from_config(
            "R",
            [
                wp("home", 50, 10, tags=[Tag.HOME]),
                wp("tgt", 50, 15, tags=[Tag.TGT]),
                wp("divert", 50, 14, tags=[Tag.DIVERT]),
                wp("home2", 50, 10, tags=[Tag.HOME]),
            ],
            conf,
        )
        report = compute_fuel(route, conf)
        assert report.return_to_divert is True
