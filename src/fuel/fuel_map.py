import yaml
import sys
from pydantic import BaseModel, Field
from pathlib import Path

is_built = getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')

fuel_map_folder_path = Path(__file__).parent.parent.parent.resolve() / 'fuel_maps' if is_built else Path('./fuel_maps')
if __name__ == '__main__':
    fuel_map_folder_path = Path('../../fuel_maps')

class FuelMapCell(BaseModel):
    speed_kts: int = Field(ge=0)
    altitude_ft: int = Field(ge=0)
    fuel_lbs_per_nm: float = Field(ge=0)

class FuelMapBySpeed(BaseModel):
    altitude: int = Field(ge=0)
    map_by_speed: dict[int, FuelMapCell] = Field()

class FuelMap(BaseModel):
    name: str = Field(min_length=3)
    capacity: int = Field(ge=0)
    fuel_map_by_altitude: dict[int, FuelMapBySpeed] = Field(min_length=1)

    @staticmethod
    def from_file(path: Path) -> 'FuelMap':
        fuel_map_path = fuel_map_folder_path / path.name
        print(f"Loading fuel map from {fuel_map_path}")
        with fuel_map_path.open('r') as f:
            data = yaml.load(f, Loader=yaml.FullLoader)
            fuel_map_by_altitude: dict[int, FuelMapBySpeed] = {}
            for row in data.get('fuelMap'):
                altitude_ft = int(row['altitude_ft'])
                speed_kts = int(row['speed_kts'])
                lb_per_nm = int(row['lb_per_nm'])
                if altitude_ft not in fuel_map_by_altitude:
                    fuel_map_by_altitude[altitude_ft] = FuelMapBySpeed(altitude=altitude_ft, map_by_speed={})
                fuel_map_by_altitude[altitude_ft].map_by_speed[speed_kts] = FuelMapCell(
                    speed_kts=speed_kts,
                    altitude_ft=altitude_ft,
                    fuel_lbs_per_nm=lb_per_nm
                )
            capacity = int(data['capacity'].replace(',', ''))
            return FuelMap(fuel_map_by_altitude=fuel_map_by_altitude, name=data['name'], capacity=capacity)

    def get_profile_key_neighbors(self, altitude: int, speed: int) -> tuple[int, int, int, int]:
        altitudes = self.fuel_map_by_altitude.keys()
        speeds: set[int] = set()
        for alt in self.fuel_map_by_altitude.values():
            for key in alt.map_by_speed.keys():
                speeds.add(key)
        altitudes_above = [a for a in altitudes if a >= altitude]
        altitudes_below = [a for a in altitudes if a <= altitude]
        altitudes_above.sort()
        altitudes_below.sort()
        speeds_above = [s for s in speeds if s >= speed]
        speeds_below = [s for s in speeds if s <= speed]
        speeds_above.sort()
        speeds_below.sort()
        altitude_low = altitudes_below[-1]
        altitude_high = altitudes_above[0]
        speed_low = speeds_below[-1]
        speed_high = speeds_above[0]
        return altitude_low, altitude_high, speed_low, speed_high

    def get_lb_per_mile_for_profile(self, altitude: int, speed: int) -> float:
        ## Performs a 2d Linear interpolation of the two neighboring speeds and two neighboring altitudes in the
        ##   fuel map, to approximate whatever set of values are passed
        (altitude_low, altitude_high, speed_low, speed_high) = self.get_profile_key_neighbors(altitude, speed)

        low_speed_low_altitude_figure = self.fuel_map_by_altitude[altitude_low].map_by_speed[speed_low].fuel_lbs_per_nm
        low_speed_high_altitude_figure = self.fuel_map_by_altitude[altitude_high].map_by_speed[speed_low].fuel_lbs_per_nm
        high_speed_low_altitude_figure = self.fuel_map_by_altitude[altitude_low].map_by_speed[speed_high].fuel_lbs_per_nm
        high_speed_high_altitude_figure = self.fuel_map_by_altitude[altitude_high].map_by_speed[speed_high].fuel_lbs_per_nm

        altitude_low_factor = 1-(altitude - altitude_low)/(altitude_high - altitude_low) if (altitude_high - altitude_low) != 0 else 1
        speed_low_factor = 1-(speed - speed_low)/(speed_high - speed_low) if (speed_high - speed_low) != 0 else 1

        low_speed_figure = (low_speed_low_altitude_figure * altitude_low_factor) + (low_speed_high_altitude_figure * (1-altitude_low_factor))
        high_speed_factor =  (high_speed_low_altitude_figure * altitude_low_factor) + (high_speed_high_altitude_figure * (1-altitude_low_factor))

        return (low_speed_figure * speed_low_factor) + (high_speed_factor * (1-speed_low_factor))

if __name__ == '__main__':
    fuel_map = FuelMap.from_file(Path('./fuel_maps/example_fuel_map.yaml'))
    print(fuel_map)
    print(fuel_map.get_lb_per_mile_for_profile(8000, 400))

