"""Board geometry: sizing, bounding boxes and coordinate transforms."""
from __future__ import annotations

import math
from dataclasses import dataclass

# Final kneeboard size (pixels).
OUTPUT_W = 1600
OUTPUT_H = 2400
BOARD_ASPECT = OUTPUT_W / OUTPUT_H  # width / height

# Extra padding around the leg so the surroundings are visible.
BOARD_MARGIN = 1.6
# Smallest board height (native pixels) so very short legs are still legible.
MIN_BOARD_HEIGHT = 1200
# Cap how far a tiny native crop may be upscaled to fill the board.
MAX_UPSCALE = 4.0
# Extra padding (fraction) added to the crop AABB.
AABB_PAD = 0.04


@dataclass
class BoardLayout:
    """Everything needed to crop, composite, draw and rotate one leg board."""

    # Leg endpoints in base-map pixels.
    prev_xy: tuple[float, float]
    cur_xy: tuple[float, float]
    centre: tuple[float, float]
    angle_deg: float  # rotation to make the leg vertical (Pillow CCW)
    board_w: float  # board size in native base pixels
    board_h: float
    # Axis-aligned crop region in base pixels.
    crop_x: int
    crop_y: int
    crop_w: int
    crop_h: int
    scale: float  # native -> canvas scale factor


def board_dimensions(leg_len_px: float) -> tuple[float, float]:
    height = max(leg_len_px * BOARD_MARGIN, MIN_BOARD_HEIGHT)
    width = height * BOARD_ASPECT
    return width, height


def _rotated_aabb(cx: float, cy: float, w: float, h: float, angle_rad: float) -> tuple[float, float, float, float]:
    cos = abs(math.cos(angle_rad))
    sin = abs(math.sin(angle_rad))
    half_w = (w / 2) * cos + (h / 2) * sin
    half_h = (w / 2) * sin + (h / 2) * cos
    return cx - half_w, cy - half_h, 2 * half_w, 2 * half_h


def compute_layout(
    prev_xy: tuple[float, float],
    cur_xy: tuple[float, float],
    image_w: int,
    image_h: int,
) -> BoardLayout:
    cx = (prev_xy[0] + cur_xy[0]) / 2
    cy = (prev_xy[1] + cur_xy[1]) / 2
    dx = cur_xy[0] - prev_xy[0]
    dy = cur_xy[1] - prev_xy[1]
    leg_len = math.hypot(dx, dy)

    board_w, board_h = board_dimensions(leg_len)

    # Rotate so the leg becomes vertical (mirrors legacy behaviour).
    angle_deg = math.degrees(math.atan2(dy, dx)) + 90
    angle_rad = math.radians(angle_deg)

    x0f, y0f, wf, hf = _rotated_aabb(cx, cy, board_w, board_h, angle_rad)
    pad_x = wf * AABB_PAD
    pad_y = hf * AABB_PAD
    x0f -= pad_x
    y0f -= pad_y
    wf += 2 * pad_x
    hf += 2 * pad_y

    # Clamp to image extents.
    x0 = max(int(math.floor(x0f)), 0)
    y0 = max(int(math.floor(y0f)), 0)
    x1 = min(int(math.ceil(x0f + wf)), image_w)
    y1 = min(int(math.ceil(y0f + hf)), image_h)
    crop_w = max(x1 - x0, 1)
    crop_h = max(y1 - y0, 1)

    scale = min(OUTPUT_W / board_w, MAX_UPSCALE)

    return BoardLayout(
        prev_xy=prev_xy,
        cur_xy=cur_xy,
        centre=(cx, cy),
        angle_deg=angle_deg,
        board_w=board_w,
        board_h=board_h,
        crop_x=x0,
        crop_y=y0,
        crop_w=crop_w,
        crop_h=crop_h,
        scale=scale,
    )


def to_canvas(xy: tuple[float, float], layout: BoardLayout) -> tuple[float, float]:
    return (
        (xy[0] - layout.crop_x) * layout.scale,
        (xy[1] - layout.crop_y) * layout.scale,
    )
