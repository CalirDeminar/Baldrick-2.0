"""Render a whole route to a folder of kneeboard cards plus a zip bundle."""
from __future__ import annotations

import os
import re
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import TYPE_CHECKING

import paths
from routes.render.cards import render_legend, render_overview
from routes.render.kneeboard import (
    format_clock,
    render_contingency,
    render_leg,
)
from units import ALTITUDE_LABEL, SPEED_LABEL

if TYPE_CHECKING:
    from config.config import Config
    from fuel.fuel import FuelReport
    from routes.map import MapSelection
    from routes.route import Route

_JPEG_QUALITY = 90


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

    def render_and_save(main_index: int) -> str:
        board = render_leg(base_image, selection, route, main_index, conf, base_pixels, flot_pixels)
        filename = f"{map_name}-wp{main_index}.jpg"
        board.save(out_dir / filename, quality=_JPEG_QUALITY)
        return filename

    leg_indices = list(range(1, main_count))
    if leg_indices:
        max_workers = min(len(leg_indices), (4))
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            list(pool.map(render_and_save, leg_indices))

    for wp in route.divert_waypoints:
        board = render_contingency(base_image, selection, route, wp, base_pixels, flot_pixels)
        safe_name = re.sub(r"[^\w\-]+", "_", wp.name).strip("_") or "divert"
        filename = f"{map_name}-divert-{safe_name}.jpg"
        board.save(out_dir / filename, quality=_JPEG_QUALITY)

    overview = render_overview(base_image, selection, route, conf, base_pixels, report, flot_pixels)
    overview.save(out_dir / f"{map_name}-Overview.jpg", quality=_JPEG_QUALITY)

    legend = render_legend(route)
    legend.save(out_dir / "Legend.jpg", quality=_JPEG_QUALITY)

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
        fuel = f"{wp.planned_fuel} lb" if wp.planned_fuel is not None else "-"
        parts.append(
            f"{wp.name.ljust(name_width)}  ETA {eta}  TAS {speed}  ESA {esa}  "
            f"PLANNED {fuel}  {tags}".rstrip()
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
        for warning in report.warnings:
            parts.append(f"  WARNING: {warning}")

    return "\n".join(parts) + "\n"
