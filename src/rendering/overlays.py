"""Pillow drawing: route lines, waypoint markers, minute ticks and doghouse."""
from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont

from shared import paths

FADED_ALPHA = 90
FOCUSED_ALPHA = 255
FLOT_COLOUR = (211, 47, 47)
TURN_WARNING_COLOUR = (255, 152, 0)


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


@lru_cache(maxsize=None)
def get_font(size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(str(paths.font_path()), size)
    except OSError:
        return ImageFont.load_default(size=size)


@dataclass
class MarkerStyle:
    radius: float
    line_width: int


def _unit(dx: float, dy: float) -> tuple[float, float]:
    length = math.hypot(dx, dy)
    if length == 0:
        return 1.0, 0.0
    return dx / length, dy / length


def _trim_polyline_outside_circle(
    points: list[tuple[float, float]],
    centre: tuple[float, float],
    radius: float,
) -> list[tuple[float, float]]:
    """Drop leading points inside the circle, clipping the first crossing
    segment exactly at the circle boundary."""
    cx, cy = centre
    first_outside = None
    for idx, (x, y) in enumerate(points):
        if math.hypot(x - cx, y - cy) >= radius:
            first_outside = idx
            break
    if first_outside is None:
        return []
    if first_outside == 0:
        return points
    x0, y0 = points[first_outside - 1]
    x1, y1 = points[first_outside]
    dx, dy = x1 - x0, y1 - y0
    fx, fy = x0 - cx, y0 - cy
    a = dx * dx + dy * dy
    b = 2.0 * (fx * dx + fy * dy)
    c = fx * fx + fy * fy - radius * radius
    disc = b * b - 4.0 * a * c
    if a <= 0 or disc < 0:
        return points[first_outside:]
    t = (-b + math.sqrt(disc)) / (2.0 * a)
    t = min(max(t, 0.0), 1.0)
    boundary = (x0 + dx * t, y0 + dy * t)
    return [boundary] + points[first_outside:]


def _marker_radius(is_ip: bool, is_tgt: bool, base_radius: float) -> float:
    if is_tgt:
        return base_radius * 0.75
    if is_ip:
        return base_radius * 0.85
    return base_radius


def draw_marker(
    draw: ImageDraw.ImageDraw,
    centre: tuple[float, float],
    track: tuple[float, float],
    is_ip: bool,
    is_tgt: bool,
    colour: tuple[int, int, int, int],
    style: MarkerStyle,
) -> None:
    cx, cy = centre
    r = _marker_radius(is_ip, is_tgt, style.radius)
    tx, ty = track
    px, py = -ty, tx  # perpendicular

    if is_tgt:
        apex = (cx + tx * r, cy + ty * r)
        left = (cx - tx * r + px * r, cy - ty * r + py * r)
        right = (cx - tx * r - px * r, cy - ty * r - py * r)
        draw.line([apex, left, right, apex], fill=colour, width=style.line_width, joint="curve")
    elif is_ip:
        corners = [
            (cx + tx * r + px * r, cy + ty * r + py * r),
            (cx + tx * r - px * r, cy + ty * r - py * r),
            (cx - tx * r - px * r, cy - ty * r - py * r),
            (cx - tx * r + px * r, cy - ty * r + py * r),
        ]
        draw.line(corners + [corners[0]], fill=colour, width=style.line_width, joint="curve")
    else:
        draw.ellipse(
            [(cx - r, cy - r), (cx + r, cy + r)],
            outline=colour,
            width=style.line_width,
        )


def draw_route(
    image: Image.Image,
    canvas_points: list[tuple[float, float]],
    tags: list[tuple[bool, bool]],
    times_hours: list[float | None],
    focused_index: int | None,
    colour_rgb: tuple[int, int, int],
    style: MarkerStyle,
    arc_polylines: list[list[tuple[float, float]] | None] | None = None,
    leg_start_points: list[tuple[float, float] | None] | None = None,
    leg_time_starts: list[float | None] | None = None,
) -> None:
    """Draw legs + markers. ``focused_index`` is the leg (into that index) drawn
    at full opacity; ``None`` (overview) draws everything focused."""
    draw = ImageDraw.Draw(image, "RGBA")
    n = len(canvas_points)

    incoming_track: list[tuple[float, float]] = [(0.0, 0.0)] * n
    for i in range(1, n):
        leg_start = (
            leg_start_points[i]
            if leg_start_points is not None and leg_start_points[i] is not None
            else canvas_points[i - 1]
        )
        incoming_track[i] = _unit(
            canvas_points[i][0] - leg_start[0],
            canvas_points[i][1] - leg_start[1],
        )
    if n > 1:
        incoming_track[0] = incoming_track[1]

    # Turn arcs leaving each waypoint (before the leg into the next index).
    if arc_polylines is not None:
        for i in range(n - 1):
            arc = arc_polylines[i]
            if not arc:
                continue
            leg_into = i + 1
            focused = focused_index is None or leg_into == focused_index
            alpha = FOCUSED_ALPHA if focused else FADED_ALPHA
            colour = (*colour_rgb, alpha)
            r = _marker_radius(tags[i][0], tags[i][1], style.radius)
            points = _trim_polyline_outside_circle(list(arc), canvas_points[i], r)
            if len(points) >= 2:
                draw.line(points, fill=colour, width=style.line_width)

    # Legs.
    for i in range(1, n):
        focused = focused_index is None or i == focused_index
        alpha = FOCUSED_ALPHA if focused else FADED_ALPHA
        colour = (*colour_rgb, alpha)
        prev = canvas_points[i - 1]
        cur = canvas_points[i]
        starts_at_arc_exit = leg_start_points is not None and leg_start_points[i] is not None
        leg_start = leg_start_points[i] if starts_at_arc_exit else prev
        tx, ty = _unit(cur[0] - leg_start[0], cur[1] - leg_start[1])
        r_prev = _marker_radius(tags[i - 1][0], tags[i - 1][1], style.radius)
        r_cur = _marker_radius(tags[i][0], tags[i][1], style.radius)
        end = (cur[0] - tx * r_cur, cur[1] - ty * r_cur)
        if starts_at_arc_exit:
            # Leg continues from the turn-arc exit point, but a shallow turn
            # can leave that exit inside the marker circle; clip to its edge.
            clipped = _trim_polyline_outside_circle([leg_start, end], prev, r_prev)
            if len(clipped) < 2:
                continue
            start = clipped[0]
        else:
            start = (leg_start[0] + tx * r_prev, leg_start[1] + ty * r_prev)
        draw.line([start, end], fill=colour, width=style.line_width)
        if focused and focused_index is not None:
            tick_start = (
                leg_time_starts[i]
                if leg_time_starts is not None and leg_time_starts[i] is not None
                else times_hours[i - 1]
            )
            _draw_minute_ticks(
                draw, leg_start, cur, tick_start, times_hours[i], colour, style
            )

    # Markers on top.
    for i in range(n):
        endpoint_of_focus = focused_index is None or i in (focused_index, focused_index - 1)
        alpha = FOCUSED_ALPHA if endpoint_of_focus else FADED_ALPHA
        colour = (*colour_rgb, alpha)
        is_ip, is_tgt = tags[i]
        draw_marker(draw, canvas_points[i], incoming_track[i], is_ip, is_tgt, colour, style)


def _draw_dashed_line(
    draw: ImageDraw.ImageDraw,
    start: tuple[float, float],
    end: tuple[float, float],
    colour: tuple[int, int, int, int],
    width: int,
    dash_len: float = 12.0,
    gap_len: float = 8.0,
    outline_colour: tuple[int, int, int, int] | None = None,
    outline_extra: int = 0,
) -> None:
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length = math.hypot(dx, dy)
    if length == 0:
        return
    tx, ty = dx / length, dy / length
    pos = 0.0
    while pos < length:
        dash_end = min(pos + dash_len, length)
        segment = [
            (start[0] + tx * pos, start[1] + ty * pos),
            (start[0] + tx * dash_end, start[1] + ty * dash_end),
        ]
        if outline_colour is not None and outline_extra > 0:
            draw.line(segment, fill=outline_colour, width=width + outline_extra * 2)
        draw.line(segment, fill=colour, width=width)
        pos += dash_len + gap_len


def draw_flot(
    image: Image.Image,
    canvas_points: list[tuple[float, float]],
    style: MarkerStyle,
) -> None:
    """Draw FLOT polyline as dashed red segments between consecutive points."""
    if len(canvas_points) < 2:
        return
    draw = ImageDraw.Draw(image, "RGBA")
    colour = (*FLOT_COLOUR, FOCUSED_ALPHA)
    width = max(style.line_width * 3, 3)
    dash_len = max(width * 4, 8)
    gap_len = max(width * 3, 6)
    outline_extra = max(2, width // 4)
    for i in range(len(canvas_points) - 1):
        _draw_dashed_line(
            draw,
            canvas_points[i],
            canvas_points[i + 1],
            colour,
            width,
            dash_len=dash_len,
            gap_len=gap_len,
            outline_colour=(0, 0, 0, FOCUSED_ALPHA),
            outline_extra=outline_extra,
        )


def draw_contingency_markers(
    image: Image.Image,
    canvas_points: list[tuple[float, float]],
    colour_rgb: tuple[int, int, int],
    style: MarkerStyle,
) -> None:
    """Draw waypoint markers only (no legs) for contingency airfields."""
    if not canvas_points:
        return
    draw = ImageDraw.Draw(image, "RGBA")
    colour = (*colour_rgb, FOCUSED_ALPHA)
    track = (1.0, 0.0)
    for centre in canvas_points:
        draw_marker(draw, centre, track, False, False, colour, style)


def _draw_minute_ticks(
    draw: ImageDraw.ImageDraw,
    prev: tuple[float, float],
    cur: tuple[float, float],
    prev_hours: float | None,
    cur_hours: float | None,
    colour: tuple[int, int, int, int],
    style: MarkerStyle,
) -> None:
    if prev_hours is None or cur_hours is None:
        return
    total_minutes = (cur_hours - prev_hours) * 60.0
    if total_minutes <= 0:
        return
    tx, ty = _unit(cur[0] - prev[0], cur[1] - prev[1])
    px, py = -ty, tx
    tick = style.radius * 0.5
    for m in range(1, int(math.floor(total_minutes)) + 1):
        f = m / total_minutes
        x = prev[0] + (cur[0] - prev[0]) * f
        y = prev[1] + (cur[1] - prev[1]) * f
        draw.line(
            [(x + px * tick, y + py * tick), (x - px * tick, y - py * tick)],
            fill=colour,
            width=max(style.line_width // 2, 1),
        )


def _doghouse_row(
    row: tuple[str, list[str]] | tuple[str, list[str], tuple[int, int, int]],
) -> tuple[str, list[str], tuple[int, int, int]]:
    if len(row) == 3:
        label, values, text_colour = row
        return label, values, text_colour
    label, values = row
    return label, values, (255, 255, 255)


def draw_doghouse(
    image: Image.Image,
    lines: list[tuple[str, list[str]] | tuple[str, list[str], tuple[int, int, int]]],
    colour_rgb: tuple[int, int, int],
) -> None:
    """Draw the info block in the bottom-left corner."""
    draw = ImageDraw.Draw(image, "RGBA")
    font_size = max(int(image.height * 0.018), 14)
    font = get_font(font_size)
    margin = int(font_size * 0.4)
    row_h = font_size + margin

    parsed = [_doghouse_row(row) for row in lines]
    label_w = max(draw.textlength(label, font=font) for label, _, _ in parsed) if parsed else 0
    value_w = 0.0
    for label, values, _ in parsed:
        for v in values:
            indent = 0 if label else label_w
            value_w = max(value_w, draw.textlength(v, font=font) - indent)
    column_gap = font_size
    total_rows = sum(len(values) for _, values, _ in parsed)
    block_w = int(label_w + column_gap + value_w + margin * 2)
    block_h = total_rows * row_h

    x0 = 0
    y0 = image.height - block_h
    draw.rectangle(
        [(x0, y0), (x0 + block_w, image.height)],
        fill=(0, 0, 0, 235),
        outline=(*colour_rgb, 255),
        width=max(int(image.width * 0.004), 2),
    )

    y = y0
    for label, values, text_colour in parsed:
        draw.line([(x0, y), (x0 + block_w, y)], fill=(255, 255, 255, 60), width=1)
        if label:
            draw.text(
                (x0 + margin, y),
                label,
                font=font,
                fill=(*text_colour, 255),
            )
        for v in values:
            vx = x0 + margin + (label_w + column_gap if label else 0)
            draw.text((vx, y), v, font=font, fill=(*text_colour, 255))
            y += row_h
