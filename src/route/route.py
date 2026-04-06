from datetime import timedelta
from pydantic import BaseModel
from pydantic import Field
from typing import Optional
from position import Position
from pathlib import Path
from enum import Enum
import yaml

from src.config import Config


class DCSMap(Enum):
    CAUCASUS = 'CAUCASUS'
    GERMANY = 'GERMANY'
    NORMANDY = 'NORMANDY'
    NTTR = 'NTTR'
    PERSIAN_GULF = 'PERSIAN_GULF'
    SYRIA = 'SYRIA'

    @staticmethod
    def from_route_waypoints(waypoints: list['Waypoint']):
        return DCSMap.CAUCASUS

class Tag(Enum):
    TGT = 'TGT'
    IP = 'IP'
    FIX = 'FIX'
    PUSH = 'PUSH'

class Waypoint(BaseModel):
    name: str = Field(min_length=1)
    timestamp: timedelta = Field()
    position: Position
    speed_to: int = Field(ge=0)
    notes: str = Field()
    minimum_leg_alt: Optional[int] = Field()
    tags: list[Tag] = Field()

    @staticmethod
    def from_dict(d: dict, conf: Config) -> 'Waypoint':
        latitude = d.get('lat').split(', ')
        longitude = d.get('long').split(', ')
        latitude = (float(latitude[0]), float(latitude[1]), float(latitude[2]))
        longitude = (float(longitude[0]), float(longitude[1]), float(longitude[2]))
        position = Position.new(latitude=latitude, longitude=longitude)

        return Waypoint(
            name=d.get('name'),
            timestamp=timedelta(),
            position=position,
            speed_to=d.get('speed_to') if d.get('speed_to') else conf.default_cruise_speed,
            notes=d.get('notes') or '',
            minimum_leg_alt=0,
            tags=d.get('tags') or [],
        )


class Route(BaseModel):
    name: str = Field(frozen=True, min_length=1)
    map: DCSMap = Field()
    start_time: timedelta = Field()
    time_on_target: timedelta = Field()
    dash_speed: int = Field(ge=0)
    default_cruise_speed: int = Field(ge=0)
    waypoints: list[Waypoint] = Field(min_length=1)

    @staticmethod
    def new(path: Path, conf: Config) -> 'Route':
        with path.open('r') as file:
            data = yaml.load(file, Loader=yaml.SafeLoader)
            print(data)
            waypoints = [
                Waypoint.from_dict(waypoint_data, conf)
                for waypoint_data in data.get('waypoints')
            ] if data.get('waypoints') else []
            return Route(
                name=data.get('name'),
                map=DCSMap.from_route_waypoints(waypoints),
                waypoints=waypoints,
                start_time=timedelta(0),
                time_on_target=timedelta(0),
                dash_speed=conf.dash_speed,
                default_cruise_speed=conf.default_cruise_speed,
            )

if __name__ == '__main__':
    config = Config.from_file(Path('../../example_config.yaml'))
    print(Route.new(Path('../../example_route_file.yaml'), config))