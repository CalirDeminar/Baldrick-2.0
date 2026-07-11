from pathlib import Path

from domain.config import Config
from parsing.route_loader import load_route
from shared.units import DistanceUnit


def _conf() -> Config:
    return Config(
        min_cruise_speed=300,
        default_cruise_speed=420,
        dash_speed=540,
        units=DistanceUnit.NAUTICAL,
    )


def test_load_route_reads_utf8_names(tmp_path: Path):
    route_yaml = tmp_path / "route.yaml"
    route_yaml.write_text(
        'name: "Zürich Strike"\n'
        "waypoints:\n"
        "  - name: Malmö\n"
        "    lat: 49, 26, 30\n"
        "    long: 07, 37, 30\n"
        "    notes: café\n"
        "  - name: Straße\n"
        "    lat: 50, 14, 30\n"
        "    long: 08, 27, 30\n",
        encoding="utf-8",
    )

    route = load_route(route_yaml, _conf())

    assert route.name == "Zürich Strike"
    assert route.waypoints[0].name == "Malmö"
    assert route.waypoints[0].notes == "café"
    assert route.waypoints[1].name == "Straße"
