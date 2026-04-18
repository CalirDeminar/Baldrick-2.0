from typing import Annotated
from datetime import timedelta
import typer
from pathlib import Path
from route.route import Route
from route.route_interactive_builder import build_route_interactive
from config.config import Config

baldrick = typer.Typer()

def timedelta_parser(arg: str) -> timedelta:
    arg = arg.strip().replace("=", "")
    [h, m, s] = arg.split(':')
    return timedelta(hours=int(h), minutes=int(m), seconds=int(s))

@baldrick.command()
def main(
        route_name: Annotated[str | None, typer.Option("--route", "-r")] = None,
        config_override: Annotated[str | None, typer.Option("--config", "-c")] = None,
        time_on_target: Annotated[timedelta | None, typer.Option("--tot", "-t", formats=["%H:%M:%S"], parser=timedelta_parser)] = None,
        push_time: Annotated[timedelta | None, typer.Option("--push", "-p", formats=["%H:%M:%S"], parser=timedelta_parser)] = None,
    ) -> None:
    conf = Config.from_file(Path('../example_config.yaml'))
    if config_override:
        conf = conf.override(config_override)
    route: Route | None = None
    if not route_name:
        route = build_route_interactive(conf)
    else:
        route_path = Path(route_name)
        route = Route.new(route_path, conf=conf)
    print(f"route: {route} config: {config_override} time: {time_on_target} push_time: {push_time}")

if __name__ == "__main__":
    typer.run(main)
# if __name__ == '__main__':
#     from config.config import Config
#     from route.route_interactive_builder import build_route_interactive
#     config = Config.from_file(Path('../example_config.yaml'))
#     build_route_interactive(config)