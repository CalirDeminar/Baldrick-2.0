from typing import TYPE_CHECKING

from pydantic import BaseModel
from pydantic import Field
from pathlib import Path
import yaml
import sys
from enum import Enum

if TYPE_CHECKING:
    from src.routes.route import Waypoint
    from position import Position

# cwd = Path(__file__).parent
# map_data_folder = cwd / 'map_data'

is_built = getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')
map_data_folder = Path(__file__).parent.parent.resolve() / 'map_data' if is_built else Path('./map_data')
print(f"map_data_folder: {map_data_folder}")

class DCSMap(Enum):
    CAUCASUS = 'CAUCASUS'
    GERMANY = 'GERMANY'
    NORMANDY = 'NORMANDY'
    NTTR = 'NTTR'
    PERSIAN_GULF = 'PERSIAN_GULF'
    SYRIA = 'SYRIA'

    @staticmethod
    def from_route_waypoints(waypoints: list['Waypoint']):
        return MapData.get_map_for_waypoints(waypoints).name

class PixelMapPoint(BaseModel):
    lat_d: float = Field()
    lon_d: float = Field()
    x_pixel: int = Field()
    y_pixel: int = Field()

class MapData(BaseModel):
    name: 'DCSMap' = Field()
    pixel_map: dict[tuple[float, float], PixelMapPoint]
    projection_adjustment_deg: float

    @property
    def bounds(self) -> tuple[tuple[float, float], tuple[float, float]]:
        max_lat = max([point.lat_d for point in self.pixel_map.values()])
        min_lat = min([point.lat_d for point in self.pixel_map.values()])
        max_long = max([point.lon_d for point in self.pixel_map.values()])
        min_long = min([point.lon_d for point in self.pixel_map.values()])
        return (min_lat, max_lat), (min_long, max_long)

    def point_within_map(self, wp: 'Position') -> bool:
        ((min_lat, max_lat), (min_long, max_long)) = self.bounds

        return (
            (min_lat <= wp.latitude.value[0] < max_lat) and
            (min_long <= wp.longitude.value[0] < max_long)
        )

    def waypoints_all_within_map(self, wps: list['Waypoint']) -> bool:
        return all([self.point_within_map(point.position) for point in wps])

    @staticmethod
    def load_map_set() -> list['MapData']:
        map_data: list['MapData'] = []
        for file in map_data_folder.iterdir():
            if file.suffix != '.yaml':
                continue
            with open(file, 'r') as f:
                pixels: dict[tuple[float, float], PixelMapPoint] = {}
                file = yaml.load(f, Loader=yaml.SafeLoader)
                pixel_data = file.get('pixel_map')
                for point in pixel_data:
                    lat_d = float(point.get('lat_d'))
                    lon_d = float(point.get('long_d'))
                    pixels[(lat_d, lon_d)] = PixelMapPoint(
                            lat_d=lat_d,
                            lon_d=lon_d,
                            x_pixel=int(point.get('x_pixel')),
                            y_pixel=int(point.get('y_pixel')),
                        )
                map_data.append(
                    MapData(
                        name=file.get('name').upper(),
                        pixel_map=pixels,
                        projection_adjustment_deg=float(file.get('projection_adjustment_deg')),
                    )
                )
        return map_data

    @staticmethod
    def get_map_for_waypoints(wps: list['Waypoint']) -> 'MapData':
        for map_val in MapData.load_map_set():
            if map_val.waypoints_all_within_map(wps):
                return map_val
        raise ValueError('Route is not fully contained within any supported map')

if __name__ == '__main__':
    loaded_set = MapData.load_map_set()
    print(loaded_set)