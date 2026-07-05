from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from enums import Tag
from errors import FuelError
from units import altitude_to_ft, distance_to_nm, speed_to_kts

if TYPE_CHECKING:
    from config.config import Config
    from routes.route import Route, Waypoint


@dataclass
class FuelReport:
    bingo_fuel: int | None
    joker_fuel: int | None
    return_to_divert: bool
    total_required: int
    capacity: int
    warnings: list[str] = field(default_factory=list)


def calculate_max_return_distance(
    route: "Route", conf: "Config", is_bingo: bool = False
) -> tuple[Tag, float] | None:
    """Furthest return distance (in route units) from any route waypoint back to
    the home airfield, or the divert airfield when it is nearer (bingo only).

    Returns ``None`` when the route has no HOME waypoint.
    """
    home_wp = next((wp for wp in route.waypoints if Tag.HOME in wp.tags), None)
    divert_wp = next((wp for wp in route.waypoints if Tag.DIVERT in wp.tags), None)
    if home_wp is None:
        return None

    max_distance = 0.0
    furthest_wp: "Waypoint | None" = None
    for wp in route.waypoints:
        if wp is home_wp or wp is divert_wp:
            continue
        distance = wp.position.distance_from(home_wp.position, route.units)
        if furthest_wp is None or distance > max_distance:
            max_distance = distance
            furthest_wp = wp

    return_type = Tag.HOME
    if is_bingo and furthest_wp is not None and divert_wp is not None:
        divert_distance = furthest_wp.position.distance_from(divert_wp.position, route.units)
        if divert_distance < max_distance:
            max_distance = divert_distance
            return_type = Tag.DIVERT
    return return_type, max_distance


def compute_fuel(route: "Route", conf: "Config") -> FuelReport:
    fuel_map = conf.active_fuel_map
    if fuel_map is None:
        raise FuelError("No fuel map is configured; set 'fuel_map' in config.yaml")

    units = route.units
    reserve = conf.reserve_fuel
    warnings: list[str] = []

    waypoints = route.waypoints
    leg_fuels: list[float] = []
    for i in range(1, len(waypoints)):
        a = waypoints[i - 1]
        b = waypoints[i]
        distance_nm = distance_to_nm(b.position.distance_from(a.position, units), units)
        altitude_ft = altitude_to_ft(b.altitude, units)
        speed_kts = speed_to_kts(b.speed_to or 0, units)
        if not fuel_map.is_within_bounds(altitude_ft, speed_kts):
            warnings.append(
                f"Leg to '{b.name}' (speed {b.speed_to}, altitude {b.altitude}) is "
                f"outside the fuel map '{fuel_map.name}' bounds "
                f"({fuel_map.bounds_description()}); using nearest approximation."
            )
        efficiency = fuel_map.get_lb_per_mile_for_profile(altitude_ft, speed_kts)
        leg_fuels.append(distance_nm * efficiency)

    # Planned fuel at each waypoint: fuel to fly all remaining legs plus reserve.
    if waypoints:
        waypoints[-1].planned_fuel = int(round(reserve))
    running = float(reserve)
    for i in range(len(waypoints) - 1, 0, -1):
        running += leg_fuels[i - 1]
        waypoints[i - 1].planned_fuel = int(round(running))

    total_required = int(round(conf.takeoff_fuel + running))

    # Bingo / joker.
    bingo_fuel: int | None = None
    joker_fuel: int | None = None
    return_to_divert = False
    rtb_alt_ft = altitude_to_ft(conf.rtb_altitude, units)
    rtb_speed_kts = speed_to_kts(conf.rtb_speed, units)
    rtb_efficiency = fuel_map.get_lb_per_mile_for_profile(rtb_alt_ft, rtb_speed_kts)
    if not fuel_map.is_within_bounds(rtb_alt_ft, rtb_speed_kts):
        warnings.append(
            f"RTB profile (speed {conf.rtb_speed}, altitude {conf.rtb_altitude}) is "
            f"outside the fuel map '{fuel_map.name}' bounds "
            f"({fuel_map.bounds_description()}); using nearest approximation."
        )

    bingo = calculate_max_return_distance(route, conf, is_bingo=True)
    if bingo is not None:
        return_type, bingo_distance = bingo
        return_to_divert = return_type == Tag.DIVERT
        bingo_nm = distance_to_nm(bingo_distance, units)
        bingo_fuel = int(round(bingo_nm * rtb_efficiency)) + reserve

        home_return = calculate_max_return_distance(route, conf, is_bingo=False)
        if home_return is not None:
            joker_nm = distance_to_nm(home_return[1], units)
            joker_fuel = int(round(joker_nm * rtb_efficiency)) + reserve
            joker_fuel = max(joker_fuel, bingo_fuel)
    else:
        warnings.append(
            "Route has no HOME waypoint; bingo/joker fuel could not be calculated."
        )

    if total_required > fuel_map.capacity:
        deficit = total_required - fuel_map.capacity
        raise FuelError(
            f"Route requires {total_required} lb of fuel (incl. {reserve} lb reserve and "
            f"{conf.takeoff_fuel} lb takeoff), but the '{fuel_map.name}' capacity is only "
            f"{fuel_map.capacity} lb (short by {deficit} lb). The route cannot be flown "
            f"without cutting into the reserve."
        )

    return FuelReport(
        bingo_fuel=bingo_fuel,
        joker_fuel=joker_fuel,
        return_to_divert=return_to_divert,
        total_required=total_required,
        capacity=fuel_map.capacity,
        warnings=warnings,
    )
