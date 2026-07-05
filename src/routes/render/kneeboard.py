"""Per-leg kneeboard board generation."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PIL import Image

from enums import Tag
from routes.render import overlays
from routes.render.compositor import composite_overlays
from routes.render.geometry import (
    OUTPUT_H,
    OUTPUT_W,
    BoardLayout,
    compute_layout,
    to_canvas,
)
from routes.render.overlays import MarkerStyle
from routes.render.vips_util import ensure_rgb, vips_to_pil
from units import ALTITUDE_LABEL, DISTANCE_LABEL, SPEED_LABEL

if TYPE_CHECKING:
    from config.config import Config
    from routes.map import MapSelection
    from routes.route import Route, Waypoint

_RESAMPLE = Image.Resampling.BICUBIC


def _hours(delta) -> float | None:
    if delta is None:
        return None
    return delta.total_seconds() / 3600.0


def format_clock(hours: float | None) -> str:
    if hours is None:
        return "N/A"
    total = int(round(hours * 3600)) % 86400
    return f"{total // 3600:02d}:{(total % 3600) // 60:02d}:{total % 60:02d}"


def format_relative(hours: float | None, push_hours: float | None) -> str | None:
    if hours is None or push_hours is None:
        return None
    total = int(round((hours - push_hours) * 3600))
    sign = "+" if total >= 0 else "-"
    total = abs(total)
    return f"{sign}{total // 3600:02d}:{(total % 3600) // 60:02d}:{total % 60:02d}"


def _dms_parts(position) -> tuple[str, str]:
    lat = position.latitude.value
    lon = position.longitude.value
    lat_h = "N" if lat[0] >= 0 else "S"
    lon_h = "E" if lon[0] >= 0 else "W"
    lat_str = f"{lat_h}{abs(int(lat[0])):02d} {int(lat[1]):02d} {int(lat[2]):02d}"
    lon_str = f"{lon_h}{abs(int(lon[0])):03d} {int(lon[1]):02d} {int(lon[2]):02d}"
    return lat_str, lon_str


def _magnetic_course(from_wp: "Waypoint", to_wp: "Waypoint", mag_var: float) -> int:
    true_course = to_wp.position.bearing_from(from_wp.position)
    return int(round((true_course - mag_var) % 360))


def build_doghouse_lines(
    route: "Route", index: int, selection: "MapSelection", conf: "Config"
) -> list[tuple[str, list[str]]]:
    wp = route.waypoints[index]
    prev = route.waypoints[index - 1]
    mag_var = selection.base.mag_var
    units = route.units

    heading = f"{_magnetic_course(prev, wp, mag_var)}\u00b0"
    if index < len(route.waypoints) - 1:
        nxt = route.waypoints[index + 1]
        next_heading = f"{_magnetic_course(wp, nxt, mag_var)}\u00b0"
    else:
        next_heading = "N/A"

    distance = wp.position.distance_from(prev.position, units)
    dist_str = f"{distance:.1f}{DISTANCE_LABEL[units]}"

    push_wp = route.push_waypoint
    push_hours = _hours(push_wp.timestamp) if push_wp else None
    eta = format_clock(_hours(wp.timestamp))
    relative = format_relative(_hours(wp.timestamp), push_hours)
    eta_values = [eta]
    if relative is not None:
        eta_values.append(f"(push {relative})")

    esa = (
        f"{wp.minimum_leg_alt:,}{ALTITUDE_LABEL[units]}"
        if wp.minimum_leg_alt is not None
        else "N/A"
    )
    tas = f"{wp.speed_to}{SPEED_LABEL[units]}" if wp.speed_to else "N/A"

    lines: list[tuple[str, list[str]]] = [
        ("WP:", [wp.name]),
        ("MC:", [heading]),
        ("DIST:", [dist_str]),
        ("ETA:", eta_values),
        ("ESA:", [esa]),
        ("TAS:", [tas]),
        ("NMC:", [next_heading]),
    ]

    notes: list[str] = []
    if wp.notes:
        notes.extend(n.strip() for n in wp.notes.split("\\n") if n.strip())
    if Tag.FIX in wp.tags:
        lat_str, lon_str = _dms_parts(wp.position)
        notes.append(f"FIX: {lat_str}")
        notes.append(f"     {lon_str}")
    if notes:
        lines.append(("", notes))
    return lines


def render_leg(
    base_image: Any,
    selection: "MapSelection",
    route: "Route",
    index: int,
    conf: "Config",
    base_pixels: list[tuple[int, int]],
) -> Image.Image:
    layout = compute_layout(
        base_pixels[index - 1], base_pixels[index], base_image.width, base_image.height
    )

    base_crop = base_image.crop(layout.crop_x, layout.crop_y, layout.crop_w, layout.crop_h)
    canvas = base_crop.resize(layout.scale) if layout.scale != 1.0 else base_crop
    canvas = composite_overlays(canvas, layout, selection)
    pil = vips_to_pil(ensure_rgb(canvas)).convert("RGBA")

    canvas_points = [to_canvas(xy, layout) for xy in base_pixels]
    tags = [(Tag.IP in wp.tags, Tag.TGT in wp.tags) for wp in route.waypoints]
    times = [_hours(wp.timestamp) for wp in route.waypoints]

    board_w_canvas = layout.board_w * layout.scale
    style = MarkerStyle(
        radius=max(board_w_canvas * 0.045, 8),
        line_width=max(int(board_w_canvas * 0.008), 2),
    )
    overlays.draw_route(pil, canvas_points, tags, times, index, _colour(route), style)

    centre = to_canvas(layout.centre, layout)
    rotated = pil.rotate(layout.angle_deg, center=centre, resample=_RESAMPLE)

    board_h_canvas = layout.board_h * layout.scale
    box = (
        centre[0] - board_w_canvas / 2,
        centre[1] - board_h_canvas / 2,
        centre[0] + board_w_canvas / 2,
        centre[1] + board_h_canvas / 2,
    )
    board = rotated.crop(tuple(int(round(v)) for v in box))

    lines = build_doghouse_lines(route, index, selection, conf)
    overlays.draw_doghouse(board, lines, _colour(route))

    return board.convert("RGB").resize((OUTPUT_W, OUTPUT_H), _RESAMPLE)


def _colour(route: "Route") -> tuple[int, int, int]:
    return overlays.hex_to_rgb(route.route_colour)
