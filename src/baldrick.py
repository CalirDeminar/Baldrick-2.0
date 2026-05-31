from typing import Annotated
from datetime import timedelta
import typer
import sys
from pathlib import Path
from routes.route import Route
from routes.route_interactive_builder import build_route_interactive
from config.config import Config

is_built = getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')

config_path = Path(__file__).parent.parent.resolve() / 'config.yaml'

route_folder_path = Path(__file__).parent.parent.resolve() / 'routes' if is_built else Path('./routes')

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
    conf = Config.from_file(config_path)
    if config_override:
        conf = conf.override(config_override)
    route: Route | None = None
    if not route_name:
        route = build_route_interactive(conf)
    else:
        route_path = Path(route_folder_path / Path(f"{route_name}.yaml"))
        route = Route.new(route_path, conf=conf)
    print(f"routes: {route} config: {config_override} time: {time_on_target} push_time: {push_time}")

if __name__ == "__main__":
    typer.run(main)
# if __name__ == '__main__':
#     from config.config import Config
#     from routes.route_interactive_builder import build_route_interactive
#     config = Config.from_file(Path('../config.yaml'))
#     build_route_interactive(config)