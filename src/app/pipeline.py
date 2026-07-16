"""End-to-end planning + rendering pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from domain.esa import compute_esa
from domain.fuel import NO_FUEL_MAP_WARNING, FuelReport, compute_fuel
from domain.tot import plan_route_times
from domain.turn_geometry import compute_turns, effective_leg_distances
from parsing.map_loader import load_map_set
from rendering import output

if TYPE_CHECKING:
    from domain.config import Config
    from domain.map import MapLayer
    from domain.route import Route


@dataclass
class PlanResult:
    out_dir: Path
    report: FuelReport | None
    warnings: list[str] = field(default_factory=list)


_MAX_TURN_PASSES = 5


def _plan_with_turns(
    route: "Route",
    conf: "Config",
    time_on_target: timedelta | None,
    push_time: timedelta | None,
) -> list[str]:
    """Iteratively reconcile leg speeds with turn-arc geometry."""
    # plan_route_times commits computed times/speeds onto the waypoints, so
    # snapshot the user-supplied constraints and restore them before each
    # re-plan; otherwise pass-1 results would be treated as hard anchors.
    original_constraints = [(wp.timestamp, wp.speed_to) for wp in route.waypoints]

    def _restore_constraints() -> None:
        for wp, (timestamp, speed_to) in zip(route.waypoints, original_constraints):
            wp.timestamp = timestamp
            wp.speed_to = speed_to

    warnings = plan_route_times(route, conf, time_on_target, push_time)
    prev_speeds: list[int | None] | None = None
    converged = False

    for _ in range(_MAX_TURN_PASSES):
        turns = compute_turns(route, conf)
        route.turn_arcs = turns
        leg_dist = effective_leg_distances(route, turns)
        current_speeds = [wp.speed_to for wp in route.main_waypoints]
        if prev_speeds is not None and current_speeds == prev_speeds:
            converged = True
            break
        prev_speeds = list(current_speeds)
        _restore_constraints()
        warnings = plan_route_times(
            route, conf, time_on_target, push_time, leg_distances=leg_dist
        )

    if not converged:
        route.turn_arcs = compute_turns(route, conf)
        warnings.append(
            "Turn geometry and time-on-target speeds did not fully converge "
            f"after {_MAX_TURN_PASSES} passes."
        )

    for i, arc in enumerate(route.turn_arcs or []):
        if arc is not None and arc.required_g is not None:
            wp_name = route.main_waypoints[i].name
            warnings.append(
                f"Turn at '{wp_name}' requires ~{arc.required_g:.1f}G "
                f"(configured {conf.turn_g:.1f}G was insufficient for the geometry)."
            )

    return warnings


def generate_kneeboards(
    route: "Route",
    conf: "Config",
    time_on_target: timedelta | None = None,
    push_time: timedelta | None = None,
    output_root: Path | None = None,
    map_chooser: Callable[[list["MapLayer"]], "MapLayer"] | None = None,
) -> PlanResult:
    warnings: list[str] = []

    selection = load_map_set().select_for(
        route.waypoints, preferred=route.map_name, chooser=map_chooser
    )
    route.map_name = selection.dcs_map
    route.time_on_target = time_on_target
    route.push_time = push_time

    warnings += _plan_with_turns(route, conf, time_on_target, push_time)
    warnings += compute_esa(route, selection, conf)

    leg_dist = (
        effective_leg_distances(route, route.turn_arcs)
        if route.turn_arcs is not None
        else None
    )
    report = compute_fuel(route, conf, leg_distances=leg_dist)
    if report is None:
        warnings.append(NO_FUEL_MAP_WARNING)
    else:
        warnings += report.warnings
        route.bingo_fuel = report.bingo_fuel
        route.joker_fuel = report.joker_fuel
        route.return_to_divert = report.return_to_divert

    out_dir = output.generate(route, selection, conf, report, output_root=output_root)
    return PlanResult(out_dir=out_dir, report=report, warnings=warnings)
