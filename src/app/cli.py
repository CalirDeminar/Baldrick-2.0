from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from app.interactive import build_route_interactive
from app.pipeline import generate_kneeboards
from parsing.config_loader import apply_override, load_config
from parsing.route_loader import load_route
from shared import paths
from shared.errors import BaldrickError

console = Console()
baldrick = typer.Typer(add_completion=False, help="Generate DCS navigation kneeboards from a route.")


def timedelta_parser(arg: str) -> timedelta:
    arg = arg.strip().replace("=", "")
    parts = arg.split(":")
    if len(parts) != 3:
        raise typer.BadParameter(f"'{arg}' must be in HH:MM:SS format")
    h, m, s = (int(p) for p in parts)
    return timedelta(hours=h, minutes=m, seconds=s)


@baldrick.command()
def main(
    route_name: Annotated[str | None, typer.Option("--route", "-r", help="Route file name (without .yaml) in the routes folder")] = None,
    config_override: Annotated[str | None, typer.Option("--config", "-c", help="Named config override to apply")] = None,
    time_on_target: Annotated[timedelta | None, typer.Option("--tot", "-t", parser=timedelta_parser, help="Time on target, HH:MM:SS")] = None,
    push_time: Annotated[timedelta | None, typer.Option("--push", "-p", parser=timedelta_parser, help="Push time, HH:MM:SS")] = None,
) -> None:
    try:
        conf = load_config()
        if config_override:
            conf = apply_override(conf, config_override)

        if route_name:
            route_path = paths.routes_dir() / f"{route_name}.yaml"
            if not route_path.exists():
                raise BaldrickError(f"Route file not found: {route_path}")
            route = load_route(route_path, conf)
        else:
            route = build_route_interactive(conf)

        console.print(f"[bold]Planning route[/bold] '{route.name}'...")
        result = generate_kneeboards(route, conf, time_on_target, push_time)

        for warning in result.warnings:
            console.print(f"[yellow]WARNING:[/yellow] {warning}")

        report = result.report
        if report.bingo_fuel is not None:
            dest = "divert" if report.return_to_divert else "home"
            console.print(f"Bingo fuel: [cyan]{report.bingo_fuel:,} lb[/cyan] (return to {dest})")
        console.print(
            f"Total fuel required: [cyan]{report.total_required:,} lb[/cyan] "
            f"of {report.capacity:,} lb capacity"
        )
        console.print(f"[green]Kneeboards written to[/green] {result.out_dir}")
    except BaldrickError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    baldrick()
