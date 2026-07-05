from typing import TYPE_CHECKING, Union, Any

from pydantic import BaseModel
from pydantic import Field
import pyvips
from pathlib import Path
import yaml
import sys
from enum import Enum
from routes.position import Position, DMSDistance
if TYPE_CHECKING:
    from src.routes.route import Waypoint

# cwd = Path(__file__).parent
# map_data_folder = cwd / 'map_data'

is_built = getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')
map_data_folder = Path(__file__).parent.parent.resolve() / 'map_data' if is_built else Path('./map_data')
image_folder = map_data_folder / 'map_data/image_files' if is_built else Path('./map_data/image_files')
if __name__ == '__main__':
    map_data_folder = Path('../../map_data')
    image_folder = map_data_folder / 'image_files'

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
    position: Position = Field()
    x_pixel: int = Field()
    y_pixel: int = Field()

class MapData(BaseModel):
    name: 'DCSMap' = Field()
    pixel_map: dict[Position, PixelMapPoint]
    projection_adjustment_deg: float
    map_image: Union[Any, None] = None

    def load_map_image(self):
        full_path = image_folder / f"{self.name.value}.jpg"
        image = pyvips.Image.new_from_file(str(full_path))
        self.map_image = image

    @property
    def bounds(self) -> tuple[tuple[float, float], tuple[float, float]]:
        max_lat = max([point.position.latitude.to_decimal() for point in self.pixel_map.values()])
        min_lat = min([point.position.latitude.to_decimal() for point in self.pixel_map.values()])
        max_long = max([point.position.longitude.to_decimal() for point in self.pixel_map.values()])
        min_long = min([point.position.longitude.to_decimal() for point in self.pixel_map.values()])
        return (min_lat, max_lat), (min_long, max_long)

    def point_within_map(self, wp: 'Position') -> bool:
        ((min_lat, max_lat), (min_long, max_long)) = self.bounds

        return (
            (min_lat <= wp.latitude.to_decimal() < max_lat) and
            (min_long <= wp.longitude.to_decimal() < max_long)
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
                    lat_d, lat_m, lat_s = point.get('lat').split(",")
                    lon_d, lon_m, lon_s = point.get('long').split(",")

                    pos = Position.new(latitude=(lat_d, lat_m, lat_s), longitude=(lon_d, lon_m, lon_s))

                    pixels[pos] = PixelMapPoint(
                            x_pixel=int(point.get('x_pixel')),
                            y_pixel=int(point.get('y_pixel')),
                            position=pos
                        )
                map_data.append(
                    MapData(
                        name=file.get('name').upper(),
                        pixel_map=pixels,
                        projection_adjustment_deg=float(file.get('projection_adjustment_deg')),
                    )
                )
        return map_data

    def get_neighboring_pixels(self, position: Position) -> tuple[PixelMapPoint, PixelMapPoint, PixelMapPoint, PixelMapPoint]:
        lat = position.latitude
        lon = position.longitude
        pixel_map_keys_sorted_latitude = sorted(self.pixel_map.keys(), key=lambda p: p.latitude.to_decimal())
        pixel_map_keys_sorted_longitude = sorted(self.pixel_map.keys(), key=lambda p: p.longitude.to_decimal())

        prev_latitude: Position | None = None
        active_latitude: tuple[DMSDistance, DMSDistance] | None = None
        for k in pixel_map_keys_sorted_latitude:
            if prev_latitude is not None and prev_latitude.latitude.to_decimal() != k.latitude.to_decimal():
                latitude_in_range = (lat.to_decimal() >= prev_latitude.latitude.to_decimal()) and (lat.to_decimal() <= k.latitude.to_decimal())
                if latitude_in_range:
                    active_latitude = prev_latitude.latitude, k.latitude
            prev_latitude = k

        prev_longitude: Position | None = None
        active_longitude: tuple[DMSDistance, DMSDistance] | None = None
        for k in pixel_map_keys_sorted_longitude:
            if prev_longitude is not None and prev_longitude.longitude.to_decimal() != k.longitude.to_decimal():
                longitude_in_range = (lon.to_decimal() >= prev_longitude.longitude.to_decimal()) and (
                            lon.to_decimal() <= k.longitude.to_decimal())
                if longitude_in_range:
                    active_longitude = prev_longitude.longitude, k.longitude
            prev_longitude = k

        keys =  (
            Position(latitude=active_latitude[0],longitude=active_longitude[0]),
            Position(latitude=active_latitude[1], longitude=active_longitude[0]),
            Position(latitude=active_latitude[0], longitude=active_longitude[1]),
            Position(latitude=active_latitude[1], longitude=active_longitude[1]),
        )
        return self.pixel_map[keys[0]], self.pixel_map[keys[1]], self.pixel_map[keys[2]], self.pixel_map[keys[3]]

    def get_pixels_for_position(self, position: Position) -> tuple[int, int]:
        lat = position.latitude.to_decimal()
        lon = position.longitude.to_decimal()

        for key, point in self.pixel_map.items():
            if key.latitude.to_decimal() == lat and key.longitude.to_decimal() == lon:
                return point.x_pixel, point.y_pixel

        sw, nw, se, ne = self.get_neighboring_pixels(position)
        lat_low = sw.position.latitude.to_decimal()
        lat_high = nw.position.latitude.to_decimal()
        lon_low = sw.position.longitude.to_decimal()
        lon_high = se.position.longitude.to_decimal()

        lat_low_factor = 1 - (lat - lat_low) / (lat_high - lat_low) if lat_high != lat_low else 1
        lon_low_factor = 1 - (lon - lon_low) / (lon_high - lon_low) if lon_high != lon_low else 1

        low_lon_x = (sw.x_pixel * lat_low_factor) + (nw.x_pixel * (1 - lat_low_factor))
        high_lon_x = (se.x_pixel * lat_low_factor) + (ne.x_pixel * (1 - lat_low_factor))
        x_pixel = (low_lon_x * lon_low_factor) + (high_lon_x * (1 - lon_low_factor))

        low_lon_y = (sw.y_pixel * lat_low_factor) + (nw.y_pixel * (1 - lat_low_factor))
        high_lon_y = (se.y_pixel * lat_low_factor) + (ne.y_pixel * (1 - lat_low_factor))
        y_pixel = (low_lon_y * lon_low_factor) + (high_lon_y * (1 - lon_low_factor))

        return round(x_pixel), round(y_pixel)


    @staticmethod
    def get_map_for_waypoints(wps: list['Waypoint']) -> 'MapData':
        for map_val in MapData.load_map_set():
            if map_val.waypoints_all_within_map(wps):
                return map_val
        raise ValueError('Route is not fully contained within any supported map')

if __name__ == '__main__':
    loaded_set = MapData.load_map_set()
    for s in loaded_set:
        s.load_map_image()
    print(loaded_set)