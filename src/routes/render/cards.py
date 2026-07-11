"""Overview and legend cards."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PIL import Image, ImageDraw

from enums import Tag
from routes.render import overlays
from routes.render.compositor import composite_overlays
from routes.render.geometry import OUTPUT_H, OUTPUT_W, BoardLayout
from routes.render.overlays import MarkerStyle, draw_marker, get_font
from routes.render.vips_util import ensure_rgb, vips_to_pil

if TYPE_CHECKING:
    from config.config import Config
    from fuel.fuel import FuelReport
    from routes.map import MapSelection
    from routes.route import Route

_RESAMPLE = Image.Resampling.BICUBIC


def render_overview(
    base_image: Any,
    selection: "MapSelection",
    route: "Route",
    conf: "Config",
    base_pixels: list[tuple[int, int]],
    report: "FuelReport | None",
    flot_pixels: list[tuple[int, int]] | None = None,
) -> Image.Image:
    xs = [p[0] for p in base_pixels]
    ys = [p[1] for p in base_pixels]
    margin_x = int((max(xs) - min(xs)) * 0.1) + 50
    margin_y = int((max(ys) - min(ys)) * 0.1) + 50

    x0 = max(min(xs) - margin_x, 0)
    y0 = max(min(ys) - margin_y, 0)
    x1 = min(max(xs) + margin_x, base_image.width)
    y1 = min(max(ys) + margin_y, base_image.height)
    crop_w = max(x1 - x0, 1)
    crop_h = max(y1 - y0, 1)

    scale = 1.0 / max(conf.overview_card_downsample_factor, 0.01)
    layout = BoardLayout(
        prev_xy=(0, 0), cur_xy=(0, 0), centre=(0, 0), angle_deg=0.0,
        board_w=crop_w, board_h=crop_h,
        crop_x=x0, crop_y=y0, crop_w=crop_w, crop_h=crop_h, scale=scale,
    )

    base_crop = base_image.crop(x0, y0, crop_w, crop_h)
    canvas = base_crop.resize(scale) if scale != 1.0 else base_crop
    canvas = composite_overlays(canvas, layout, selection)
    pil = vips_to_pil(ensure_rgb(canvas)).convert("RGBA")

    canvas_points = [((x - x0) * scale, (y - y0) * scale) for (x, y) in base_pixels]
    main = route.main_waypoints
    main_indices = [i for i, wp in enumerate(route.waypoints) if Tag.DIVERT not in wp.tags]
    main_points = [canvas_points[i] for i in main_indices]
    tags = [(Tag.IP in wp.tags, Tag.TGT in wp.tags) for wp in main]
    times = [None for _ in main]

    style = MarkerStyle(
        radius=max(pil.width * 0.02, 6),
        line_width=max(int(pil.width * 0.004), 2),
    )
    overlays.draw_route(
        pil, main_points, tags, times, None, overlays.hex_to_rgb(route.route_colour), style
    )
    divert_points = [
        canvas_points[i] for i, wp in enumerate(route.waypoints) if Tag.DIVERT in wp.tags
    ]
    if divert_points:
        overlays.draw_contingency_markers(
            pil, divert_points, overlays.hex_to_rgb(route.route_colour), style
        )

    if flot_pixels:
        flot_points = [((x - x0) * scale, (y - y0) * scale) for (x, y) in flot_pixels]
        overlays.draw_flot(pil, flot_points, style)

    _draw_overview_summary(pil, route, selection, report)
    return pil.convert("RGB")


def _draw_overview_summary(
    image: Image.Image, route: "Route", selection: "MapSelection", report: "FuelReport | None"
) -> None:
    lines: list[tuple[str, list[str]]] = [
        ("Route:", [route.name]),
        ("Map:", [selection.base.name]),
    ]
    if report is not None:
        if report.bingo_fuel is not None:
            dest = "divert" if report.return_to_divert else "home"
            lines.append(("Bingo:", [f"{report.bingo_fuel:,} lb ({dest})"]))
        if report.joker_fuel is not None:
            lines.append(("Joker:", [f"{report.joker_fuel:,} lb"]))
        if report.aar_topups:
            tanker_lines = [
                f"{t.name}: {t.route_min:,} / {report.post_aar_capacity:,} lb"
                for t in report.aar_topups
            ]
            lines.append(("Tanker:", tanker_lines))
        lines.append(("Fuel:", [f"{report.total_required:,} / {report.capacity:,} lb"]))
    overlays.draw_doghouse(image, lines, overlays.hex_to_rgb(route.route_colour))


def render_legend(route: "Route") -> Image.Image:
    image = Image.new("RGB", (OUTPUT_W, OUTPUT_H), (245, 245, 245))
    draw = ImageDraw.Draw(image, "RGBA")
    colour = overlays.hex_to_rgb(route.route_colour)
    title_font = get_font(80)
    font = get_font(48)

    draw.text((60, 60), "Legend", font=title_font, fill=(0, 0, 0, 255))

    entries = [
        ("waypoint", False, False, "Waypoint"),
        ("ip", True, False, "IP (initial point)"),
        ("tgt", False, True, "Target"),
    ]
    style = MarkerStyle(radius=48, line_width=10)
    y = 240
    for _, is_ip, is_tgt, label in entries:
        draw_marker(draw, (120, y), (1.0, 0.0), is_ip, is_tgt, (*colour, 255), style)
        draw.text((220, y - 30), label, font=font, fill=(0, 0, 0, 255))
        y += 160

    draw.line([(60, y), (180, y)], fill=(*colour, 255), width=10)
    draw.text((220, y - 30), "Route leg", font=font, fill=(0, 0, 0, 255))
    y += 160

    flot_style = MarkerStyle(radius=48, line_width=10)
    overlays.draw_flot(image, [(60, y), (180, y)], flot_style)
    draw.text((220, y - 30), "FLOT (forward line of own troops)", font=font, fill=(0, 0, 0, 255))
    y += 160

    doghouse_help = [
        "WP  - waypoint name",
        "MC  - magnetic course for the leg",
        "DIST- leg distance",
        "ETA - time on target (and relative to push)",
        "ESA - emergency safe altitude",
        "TAS - true airspeed for the leg",
        "NMC - magnetic course for the next leg",
        "Red FLOT CROSSED warning on legs that cross the FLOT",
    ]
    draw.text((60, y), "Doghouse fields:", font=font, fill=(0, 0, 0, 255))
    y += 80
    for entry in doghouse_help:
        draw.text((80, y), entry, font=font, fill=(0, 0, 0, 255))
        y += 70

    return image
