from pathlib import Path

import pytest

from domain.config import Config
from parsing.route_loader import load_route
from shared.errors import BaldrickError
from shared.units import DistanceUnit


def _conf() -> Config:
    return Config(
        min_cruise_speed=300,
        default_cruise_speed=420,
        dash_speed=540,
        units=DistanceUnit.NAUTICAL,
    )


def _write_route(path: Path, extra: str = "") -> Path:
    path.write_text(
        "name: Test\n"
        f"{extra}"
        "waypoints:\n"
        "  - name: A\n"
        "    lat: 49, 0, 0\n"
        "    long: 08, 0, 0\n"
        "  - name: B\n"
        "    lat: 50, 0, 0\n"
        "    long: 09, 0, 0\n",
        encoding="utf-8",
    )
    return path


def test_load_route_reads_magvar(tmp_path: Path):
    route = load_route(_write_route(tmp_path / "route.yaml", extra="magvar: -13\n"), _conf())
    assert route.magvar == -13.0


def test_load_route_magvar_defaults_unset(tmp_path: Path):
    route = load_route(_write_route(tmp_path / "route.yaml"), _conf())
    assert route.magvar is None


def test_load_route_rejects_invalid_magvar(tmp_path: Path):
    with pytest.raises(BaldrickError, match="Invalid magvar"):
        load_route(_write_route(tmp_path / "route.yaml", extra="magvar: east\n"), _conf())
