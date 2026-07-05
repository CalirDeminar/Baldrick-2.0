"""Time-on-target / leg-speed planner.

Given a route whose waypoints may carry a mix of fixed timestamps (anchors) and
fixed leg speeds, plus optional command-line ToT (at the target) and push time,
this assigns a concrete timestamp and leg speed to every waypoint.

Design goals (see docs/architecture_notes.md):
- Honour hard constraints first: fixed timestamps, fixed leg speeds, and the
  dash speed on the IP -> target leg.
- Prefer cruise speeds that are multiples of 60 (1 unit / minute granularity)
  by absorbing slack as a hold, but fall back to an exact speed when no
  multiple-of-60 speed can hit an anchor.
- Raise descriptive errors when anchors are inconsistent or impossible.
"""
from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from enums import Tag
from errors import ToTError

if TYPE_CHECKING:
    from config.config import Config
    from routes.route import Route

# Tolerance (hours) when matching anchor times exactly.
_TOL = 1e-6
# A leg/segment longer than this many hours is treated as an input error rather
# than a legitimate midnight wrap.
_MAX_SEGMENT_HOURS = 12.0


def _speed_options(min_cruise: int) -> list[int]:
    options = [s for s in range(60, 3001, 60) if s >= max(min_cruise, 1)]
    return options or [max(min_cruise, 60)]


def _last_index_with_tag(route: "Route", tag: Tag) -> int | None:
    idx = None
    for i, wp in enumerate(route.waypoints):
        if tag in wp.tags:
            idx = i
    return idx


def plan_route_times(
    route: "Route",
    conf: "Config",
    time_on_target: timedelta | None = None,
    push_time: timedelta | None = None,
) -> list[str]:
    """Assign timestamps + leg speeds to every waypoint in ``route``.

    Returns a list of non-fatal warnings.
    """
    wps = route.waypoints
    n = len(wps)
    warnings: list[str] = []
    if n == 0:
        return warnings

    units = route.units
    default_cruise = conf.default_cruise_speed
    min_cruise = conf.min_cruise_speed
    options = _speed_options(min_cruise)

    dist = [0.0] * n
    for i in range(1, n):
        dist[i] = wps[i].position.distance_from(wps[i - 1].position, units)

    tgt_idx = _last_index_with_tag(route, Tag.TGT)
    push_idx = _last_index_with_tag(route, Tag.PUSH)

    # Fixed leg speed for the leg *into* waypoint i (None => free/cruise).
    fixed_speed: list[float | None] = [None] * n
    for i in range(1, n):
        if wps[i].speed_to is not None:
            fixed_speed[i] = float(wps[i].speed_to)
        elif tgt_idx is not None and i == tgt_idx:
            fixed_speed[i] = float(conf.dash_speed)

    # Collect anchors (index -> hours) from fixed timestamps + CLI overrides.
    anchor: dict[int, float] = {}
    for i, wp in enumerate(wps):
        if wp.timestamp is not None:
            anchor[i] = wp.timestamp.total_seconds() / 3600.0
    if time_on_target is not None:
        if tgt_idx is None:
            warnings.append("--tot was supplied but the route has no TGT waypoint; ignoring it.")
        else:
            anchor[tgt_idx] = time_on_target.total_seconds() / 3600.0
    if push_time is not None:
        if push_idx is None:
            warnings.append("--push was supplied but the route has no PUSH waypoint; ignoring it.")
        else:
            anchor[push_idx] = push_time.total_seconds() / 3600.0

    times: list[float | None] = [None] * n
    speeds: list[int] = [0] * n

    if not anchor:
        _plan_unanchored(wps, dist, fixed_speed, default_cruise, times, speeds)
        warnings.append(
            "No time-on-target or timed waypoints supplied; used the default cruise speed."
        )
        _commit(wps, times, speeds)
        return warnings

    norm = _normalise_anchors(wps, anchor)

    anchored = sorted(norm)
    for idx in anchored:
        times[idx] = norm[idx]

    first_anchor = anchored[0]
    last_anchor = anchored[-1]

    # Leading legs before the first anchor: cruise/fixed, back-propagated.
    for i in range(first_anchor, 0, -1):
        s = fixed_speed[i] if fixed_speed[i] is not None else float(default_cruise)
        speeds[i] = int(round(s))
        times[i - 1] = times[i] - (dist[i] / s if s else 0.0)

    # Interior segments between consecutive anchors.
    for a, b in zip(anchored, anchored[1:]):
        seg_warnings = _solve_segment(
            wps, dist, fixed_speed, options, min_cruise, default_cruise, a, b, norm, times, speeds
        )
        warnings.extend(seg_warnings)

    # Trailing legs after the last anchor: cruise/fixed, forward.
    for i in range(last_anchor + 1, n):
        s = fixed_speed[i] if fixed_speed[i] is not None else float(default_cruise)
        speeds[i] = int(round(s))
        times[i] = times[i - 1] + (dist[i] / s if s else 0.0)

    _commit(wps, times, speeds)
    return warnings


def _plan_unanchored(wps, dist, fixed_speed, default_cruise, times, speeds) -> None:
    times[0] = 0.0
    for i in range(1, len(wps)):
        s = fixed_speed[i] if fixed_speed[i] is not None else float(default_cruise)
        speeds[i] = int(round(s))
        times[i] = times[i - 1] + (dist[i] / s if s else 0.0)


def _normalise_anchors(wps, anchor: dict[int, float]) -> dict[int, float]:
    """Make anchor times strictly increasing, treating a small backwards step as
    a midnight wrap (+24h) and a large one as an error."""
    norm: dict[int, float] = {}
    offset = 0.0
    prev_t: float | None = None
    prev_idx: int | None = None
    for idx in sorted(anchor):
        t = anchor[idx] + offset
        if prev_t is not None:
            if abs(t - prev_t) < _TOL:
                raise ToTError(
                    f"Waypoints '{wps[prev_idx].name}' and '{wps[idx].name}' have the "
                    f"same time-on-target."
                )
            while t < prev_t:
                t += 24.0
                offset += 24.0
            if t - prev_t > _MAX_SEGMENT_HOURS:
                raise ToTError(
                    f"The time between waypoints '{wps[prev_idx].name}' and "
                    f"'{wps[idx].name}' is unreasonably large ({t - prev_t:.1f} h); "
                    f"check their timestamps."
                )
        norm[idx] = t
        prev_t = t
        prev_idx = idx
    return norm


def _solve_segment(
    wps, dist, fixed_speed, options, min_cruise, default_cruise, a, b, norm, times, speeds
) -> list[str]:
    warnings: list[str] = []
    available = norm[b] - norm[a]
    legs = range(a + 1, b + 1)

    fixed_time = 0.0
    free_dist = 0.0
    for i in legs:
        if fixed_speed[i] is not None:
            s = fixed_speed[i]
            fixed_time += dist[i] / s if s else 0.0
        else:
            free_dist += dist[i]

    free_time_available = available - fixed_time
    seg_names = f"'{wps[a].name}' -> '{wps[b].name}'"

    if free_time_available < -_TOL:
        raise ToTError(
            f"Segment {seg_names} is impossible: the fixed-speed legs alone take "
            f"longer than the {available:.2f} h allowed between their times."
        )

    hold = 0.0
    free_speed = float(default_cruise)
    if free_dist <= _TOL:
        # No free legs: any leftover time becomes a hold at the start of the segment.
        hold = max(free_time_available, 0.0)
    elif free_time_available <= _TOL:
        raise ToTError(
            f"Segment {seg_names} is impossible: there is no time left for its "
            f"cruise legs after the fixed-speed legs."
        )
    else:
        candidates = [s for s in options if (free_dist / s) <= free_time_available + _TOL]
        if candidates:
            free_speed = float(min(candidates))
            hold = free_time_available - (free_dist / free_speed)
        else:
            free_speed = free_dist / free_time_available
            hold = 0.0
            warnings.append(
                f"Segment {seg_names} could not keep a multiple-of-60 cruise speed; "
                f"using {free_speed:.0f} to meet the required time."
            )

    running = norm[a] + hold
    for i in legs:
        s = fixed_speed[i] if fixed_speed[i] is not None else free_speed
        speeds[i] = int(round(s))
        running += dist[i] / s if s else 0.0
        times[i] = running
    times[b] = norm[b]
    return warnings


def _commit(wps, times, speeds) -> None:
    for i, wp in enumerate(wps):
        t = times[i] if times[i] is not None else 0.0
        wp.timestamp = timedelta(hours=t)
        wp.speed_to = speeds[i]
