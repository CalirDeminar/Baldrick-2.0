"""Render a whole route to a folder of kneeboard cards plus a zip bundle."""
from __future__ import annotations

import os
import re
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image

from shared import paths
from domain.config import effective_card_alpha
from domain.fuel import NO_FUEL_MAP_WARNING
from rendering.cards import render_legend, render_overview
from rendering.kneeboard import (
    format_clock,
    render_contingency,
    render_leg,
)
from shared.units import ALTITUDE_LABEL, SPEED_LABEL

if TYPE_CHECKING:
    from domain.config import Config
    from domain.fuel import FuelReport
    from domain.map import MapSelection
    from domain.route import Route

_JPEG_QUALITY = 90


def finalize_card(image: Image.Image, card_alpha: int) -> tuple[Image.Image, str]:
    """Return (image, extension). 'jpg' when opaque, 'png' when transparent."""
    if card_alpha >= 255:
        return image.convert("RGB"), "jpg"
    rgba = image.convert("RGBA")
    r, g, b, a = rgba.split()
    scale = card_alpha / 255.0
    a = a.point(lambda p: int(p * scale))
    return Image.merge("RGBA", (r, g, b, a)), "png"


def _save_card(image: Image.Image, path_stem: Path, card_alpha: int) -> str:
    finalized, ext = finalize_card(image, card_alpha)
    filename = f"{path_stem.name}.{ext}"
    path = path_stem.parent / filename
    if ext == "jpg":
        finalized.save(path, quality=_JPEG_QUALITY)
    else:
        finalized.save(path)
    return filename


def generate(
    route: "Route",
    selection: "MapSelection",
    conf: "Config",
    report: "FuelReport | None" = None,
    output_root: Path | None = None,
) -> Path:
    output_root = output_root or paths.output_dir()
    out_dir = output_root / route.name
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    base_image = selection.base.load_image()
    base_pixels = [selection.base.get_pixels_for_position(wp.position) for wp in route.waypoints]
    flot_pixels = [selection.base.get_pixels_for_position(p) for p in route.flot]

    map_name = selection.base.name.upper()
    main_count = len(route.main_waypoints)
    card_alpha = effective_card_alpha(conf)

    def render_and_save(main_index: int) -> str:
        board = render_leg(
            base_image, selection, route, main_index, conf, base_pixels, flot_pixels, report
        )
        stem = out_dir / f"{map_name}-02-wp{main_index:02d}"
        return _save_card(board, stem, card_alpha)

    leg_indices = list(range(1, main_count))
    if leg_indices:
        max_workers = min(len(leg_indices), (4))
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            list(pool.map(render_and_save, leg_indices))

    for wp in route.divert_waypoints:
        board = render_contingency(base_image, selection, route, wp, base_pixels, flot_pixels)
        safe_name = re.sub(r"[^\w\-]+", "_", wp.name).strip("_") or "divert"
        _save_card(board, out_dir / f"{map_name}-03-divert-{safe_name}", card_alpha)

    overview = render_overview(base_image, selection, route, conf, base_pixels, report, flot_pixels)
    _save_card(overview, out_dir / f"{map_name}-01-Overview", card_alpha)

    legend = render_legend(route)
    _save_card(legend, out_dir / f"{map_name}-00-Legend", card_alpha)

    (out_dir / "notes.txt").write_text(_write_notes(route, selection, conf, report), encoding="utf-8")

    archive = shutil.make_archive(str(output_root / route.name), "zip", root_dir=out_dir)
    shutil.move(archive, out_dir / f"{route.name}.zip")

    return out_dir


def _write_notes(
    route: "Route", selection: "MapSelection", conf: "Config", report: "FuelReport | None"
) -> str:
    units = route.units
    parts: list[str] = [f"Route: {route.name}", f"Map: {selection.base.name}", ""]

    name_width = max((len(wp.name) for wp in route.main_waypoints), default=4)
    for wp in route.main_waypoints:
        eta = format_clock(wp.timestamp.total_seconds() / 3600.0 if wp.timestamp else None)
        tags = ", ".join(t.value for t in wp.tags)
        speed = f"{wp.speed_to}{SPEED_LABEL[units]}" if wp.speed_to else "-"
        esa = f"{wp.minimum_leg_alt}{ALTITUDE_LABEL[units]}" if wp.minimum_leg_alt is not None else "-"
        fuel = f"{wp.min_fuel} lb" if wp.min_fuel is not None else "-"
        parts.append(
            f"{wp.name.ljust(name_width)}  ETA {eta}  TAS {speed}  ESA {esa}  "
            f"MIN FUEL {fuel}  {tags}".rstrip()
        )

    if route.divert_waypoints:
        parts += ["", "Contingency:"]
        for wp in route.divert_waypoints:
            notes = wp.notes.replace("\\n", " / ") if wp.notes else ""
            parts.append(f"  {wp.name}  DIVERT  {notes}".rstrip())

    if report is not None:
        parts += ["", "Fuel:"]
        if report.bingo_fuel is not None:
            dest = "divert" if report.return_to_divert else "home"
            parts.append(f"  Bingo: {report.bingo_fuel} lb (return to {dest})")
        if report.joker_fuel is not None:
            parts.append(f"  Joker: {report.joker_fuel} lb")
        parts.append(f"  Total required: {report.total_required} lb of {report.capacity} lb capacity")
        if report.aar_topups:
            parts += ["", "Tanker:"]
            for topup in report.aar_topups:
                parts.append(
                    f"  {topup.name}  min leaving {topup.route_min} lb of "
                    f"{report.post_aar_capacity} lb usable after top-up"
                )
        for warning in report.warnings:
            parts.append(f"  WARNING: {warning}")
    else:
        parts += ["", "Fuel:", f"  WARNING: {NO_FUEL_MAP_WARNING}"]

    return "\n".join(parts) + "\n"
