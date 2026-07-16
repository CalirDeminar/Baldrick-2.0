"""Turn-arc geometry between route legs."""
from __future__ import annotations

import math
from enum import Enum
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from domain.position import Position
from shared.units import DistanceUnit, distance_to_nm, speed_to_kts

if TYPE_CHECKING:
    from domain.config import Config
    from domain.route import Route

_GRAVITY = 9.80665
_NM_TO_M = 1852.0
_M_PER_DEG_LAT = 111_320.0
_HEADING_CHANGE_MIN_DEG = 1.0
_ARC_SAMPLE_DEG = 3.0


class TurnDirection(str, Enum):
    LEFT = "left"
    RIGHT = "right"


class TurnArc(BaseModel):
    """Turn flown immediately after passing a waypoint."""

    exit_point: Position
    radius: float
    arc_length: float
    direction: TurnDirection
    required_g: float | None = Field(default=None)
    arc_points: list[Position] = Field(default_factory=list)


def _meters_to_route_units(meters: float, units: DistanceUnit) -> float:
    nm = meters / _NM_TO_M
    if units == DistanceUnit.METRIC:
        return nm / (1.0 / 1.852)
    if units == DistanceUnit.IMPERIAL:
        return nm / (1.0 / 1.150779448)
    return nm


def _route_units_to_meters(value: float, units: DistanceUnit) -> float:
    return distance_to_nm(value, units) * _NM_TO_M


def _to_local(origin: Position, point: Position) -> tuple[float, float]:
    lat0, lon0 = origin.to_decimal()
    lat, lon = point.to_decimal()
    lat_rad = math.radians(lat0)
    dy = (lat - lat0) * _M_PER_DEG_LAT
    dx = (lon - lon0) * _M_PER_DEG_LAT * math.cos(lat_rad)
    return dx, dy


def _from_local(origin: Position, dx: float, dy: float) -> Position:
    lat0, lon0 = origin.to_decimal()
    lat_rad = math.radians(lat0)
    dlat = dy / _M_PER_DEG_LAT
    dlon = dx / (_M_PER_DEG_LAT * math.cos(lat_rad))
    return Position.from_decimal(lat0 + dlat, lon0 + dlon)


def _unit(dx: float, dy: float) -> tuple[float, float]:
    length = math.hypot(dx, dy)
    if length == 0:
        return 1.0, 0.0
    return dx / length, dy / length


def _heading_change_deg(inbound_bearing: float, outbound_bearing: float) -> float:
    diff = (outbound_bearing - inbound_bearing + 180.0) % 360.0 - 180.0
    return abs(diff)


def _turn_radius_m(
    speed: float,
    units: DistanceUnit,
    turn_g: float,
    rate_deg_s: float | None,
) -> float:
    speed_kts = speed_to_kts(speed, units)
    v_mps = speed_kts * _NM_TO_M / 3600.0
    r_g = v_mps**2 / (_GRAVITY * math.sqrt(turn_g**2 - 1.0))
    if rate_deg_s is not None:
        omega = math.radians(rate_deg_s)
        r_rate = v_mps / omega
        return max(r_g, r_rate)
    return r_g


def _required_g_from_radius_m(v_mps: float, radius_m: float) -> float:
    lateral = v_mps**2 / (_GRAVITY * radius_m)
    return math.sqrt(1.0 + lateral * lateral)


def _ccw_sweep(start: float, end: float) -> float:
    return (end - start) % (2.0 * math.pi)


def _cw_sweep(start: float, end: float) -> float:
    return (start - end) % (2.0 * math.pi)


def _tangent_points(
    px: float, py: float, cx: float, cy: float, radius: float
) -> list[tuple[float, float]]:
    dx, dy = px - cx, py - cy
    dist = math.hypot(dx, dy)
    if dist <= radius:
        return []
    ux, uy = dx / dist, dy / dist
    alpha = math.asin(radius / dist)
    base = math.atan2(dy, dx)
    angles = (base + math.pi / 2.0 - alpha, base - math.pi / 2.0 + alpha)
    return [(cx + radius * math.cos(a), cy + radius * math.sin(a)) for a in angles]


def _sample_arc(
    origin: Position,
    centre: tuple[float, float],
    radius_m: float,
    theta_start: float,
    theta_end: float,
    ccw: bool,
) -> list[Position]:
    if ccw:
        sweep = _ccw_sweep(theta_start, theta_end)
    else:
        sweep = _cw_sweep(theta_start, theta_end)
    if sweep < math.radians(_HEADING_CHANGE_MIN_DEG):
        return []
    steps = max(int(math.degrees(sweep) / _ARC_SAMPLE_DEG), 2)
    cx, cy = centre
    points: list[Position] = []
    for i in range(steps + 1):
        f = i / steps
        if ccw:
            theta = (theta_start + sweep * f) % (2.0 * math.pi)
        else:
            theta = (theta_start - sweep * f) % (2.0 * math.pi)
        lx = cx + radius_m * math.cos(theta)
        ly = cy + radius_m * math.sin(theta)
        points.append(_from_local(origin, lx, ly))
    return points


def _compute_single_turn(
    inbound_start: Position,
    waypoint: Position,
    next_wp: Position,
    speed: float,
    units: DistanceUnit,
    turn_g: float,
    rate_deg_s: float | None,
) -> TurnArc | None:
    inbound_bearing = waypoint.bearing_from(inbound_start)
    outbound_bearing = next_wp.bearing_from(waypoint)
    if _heading_change_deg(inbound_bearing, outbound_bearing) < _HEADING_CHANGE_MIN_DEG:
        return None

    origin = waypoint
    start_x, start_y = _to_local(origin, inbound_start)
    next_x, next_y = _to_local(origin, next_wp)

    tx, ty = _unit(-start_x, -start_y)
    if math.hypot(start_x, start_y) < 1.0:
        tx, ty = _unit(next_x, next_y)

    cross = tx * next_y - ty * next_x
    if abs(cross) < 1e-9:
        return None

    turn_left = cross > 0
    direction = TurnDirection.LEFT if turn_left else TurnDirection.RIGHT
    nx, ny = (-ty, tx) if turn_left else (ty, -tx)

    speed_kts = speed_to_kts(speed, units)
    v_mps = speed_kts * _NM_TO_M / 3600.0
    radius_m = _turn_radius_m(speed, units, turn_g, rate_deg_s)

    dot_dn = next_x * nx + next_y * ny
    if dot_dn <= 0:
        return None
    max_radius_m = (next_x * next_x + next_y * next_y) / (2.0 * dot_dn)

    required_g: float | None = None
    if radius_m > max_radius_m:
        radius_m = max_radius_m
        required_g = _required_g_from_radius_m(v_mps, radius_m)

    cx, cy = radius_m * nx, radius_m * ny
    tangents = _tangent_points(next_x, next_y, cx, cy, radius_m)
    if not tangents:
        return None

    theta_entry = math.atan2(-cy, -cx)
    best: tuple[float, float, float] | None = None
    for tx_pt, ty_pt in tangents:
        theta_exit = math.atan2(ty_pt - cy, tx_pt - cx)
        if turn_left:
            sweep = _ccw_sweep(theta_entry, theta_exit)
            exit_vx, exit_vy = -math.sin(theta_exit), math.cos(theta_exit)
        else:
            sweep = _cw_sweep(theta_entry, theta_exit)
            exit_vx, exit_vy = math.sin(theta_exit), -math.cos(theta_exit)
        to_next_x, to_next_y = next_x - tx_pt, next_y - ty_pt
        to_len = math.hypot(to_next_x, to_next_y)
        if to_len < 1e-6:
            continue
        align = (exit_vx * to_next_x + exit_vy * to_next_y) / to_len
        if align < 0.5:
            continue
        if best is None or sweep < best[2]:
            best = (tx_pt, ty_pt, sweep)

    if best is None:
        return None

    exit_x, exit_y, sweep = best
    arc_points = _sample_arc(
        origin,
        (cx, cy),
        radius_m,
        theta_entry,
        math.atan2(exit_y - cy, exit_x - cx),
        ccw=turn_left,
    )
    if not arc_points:
        return None

    exit_point = _from_local(origin, exit_x, exit_y)
    radius = _meters_to_route_units(radius_m, units)
    arc_length = _meters_to_route_units(radius_m * sweep, units)

    return TurnArc(
        exit_point=exit_point,
        radius=radius,
        arc_length=arc_length,
        direction=direction,
        required_g=required_g,
        arc_points=arc_points,
    )


def compute_turns(route: "Route", conf: "Config") -> list[TurnArc | None]:
    """Return one entry per main-route waypoint (None where no turn applies)."""
    wps = route.main_waypoints
    n = len(wps)
    turns: list[TurnArc | None] = [None] * n
    if n < 3:
        return turns

    for i in range(1, n - 1):
        inbound_start = (
            turns[i - 1].exit_point if turns[i - 1] is not None else wps[i - 1].position
        )
        speed = wps[i].speed_to or conf.default_cruise_speed
        turns[i] = _compute_single_turn(
            inbound_start,
            wps[i].position,
            wps[i + 1].position,
            speed,
            route.units,
            conf.turn_g,
            conf.turn_rate_deg_per_sec,
        )
    return turns


def effective_leg_distances(route: "Route", turns: list[TurnArc | None]) -> list[float]:
    """Distance for each leg into waypoint index i (index 0 unused / zero)."""
    wps = route.main_waypoints
    n = len(wps)
    dist = [0.0] * n
    for i in range(1, n):
        arc_len = turns[i - 1].arc_length if turns[i - 1] is not None else 0.0
        if turns[i - 1] is not None:
            start = turns[i - 1].exit_point
        else:
            start = wps[i - 1].position
        straight = wps[i].position.distance_from(start, route.units)
        dist[i] = straight + arc_len
    return dist


def leg_start_position(
    route: "Route", turns: list[TurnArc | None], leg_index: int
) -> Position:
    """Geographic start of the straight segment for the leg into ``leg_index``."""
    wps = route.main_waypoints
    if leg_index <= 0:
        return wps[0].position
    if turns[leg_index - 1] is not None:
        return turns[leg_index - 1].exit_point
    return wps[leg_index - 1].position
