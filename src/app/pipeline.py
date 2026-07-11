"""End-to-end planning + rendering pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from domain.esa import compute_esa
from domain.fuel import FuelReport, compute_fuel
from domain.tot import plan_route_times
from parsing.map_loader import load_map_set
from rendering import output

if TYPE_CHECKING:
    from domain.config import Config
    from domain.route import Route


@dataclass
class PlanResult:
    out_dir: Path
    report: FuelReport
    warnings: list[str] = field(default_factory=list)


def generate_kneeboards(
    route: "Route",
    conf: "Config",
    time_on_target: timedelta | None = None,
    push_time: timedelta | None = None,
    output_root: Path | None = None,
) -> PlanResult:
    warnings: list[str] = []

    selection = load_map_set().select_for(route.waypoints)
    route.map_name = selection.dcs_map
    route.time_on_target = time_on_target
    route.push_time = push_time

    warnings += plan_route_times(route, conf, time_on_target, push_time)
    warnings += compute_esa(route, selection, conf)

    report = compute_fuel(route, conf)
    warnings += report.warnings
    route.bingo_fuel = report.bingo_fuel
    route.joker_fuel = report.joker_fuel
    route.return_to_divert = report.return_to_divert

    out_dir = output.generate(route, selection, conf, report, output_root=output_root)
    return PlanResult(out_dir=out_dir, report=report, warnings=warnings)
