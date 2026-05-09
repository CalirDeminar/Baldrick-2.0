from pydantic import BaseModel
from pydantic import Field
from pathlib import Path
from enum import Enum
import yaml

from fuel.fuel_map import FuelMap


class DistanceUnit(Enum):
    NAUTICAL = "NAUTICAL"
    METRIC = "METRIC"
    IMPERIAL = "IMPERIAL"

class ConfigOverride(BaseModel):
    name: str = Field(min_length=1)
    route_colour: str | None = Field(default="#000000")
    min_cruise_speed: int | None = Field(ge=0)
    default_cruise_speed: int | None = Field(ge=0)
    dash_speed: int | None = Field(ge=0)
    units: DistanceUnit | None = Field()
    fuel_map: str | None = Field(default=None)

class Config(BaseModel):
    overview_card_downsample_factor: float = Field(ge=0, default=3)
    route_colour: str = Field(default="#000000")
    min_cruise_speed: int = Field(ge=0)
    default_cruise_speed: int = Field(ge=0)
    dash_speed: int = Field(ge=0)
    units: DistanceUnit = Field(default=DistanceUnit.NAUTICAL)
    overrides: list[ConfigOverride] = Field(default=[])
    # Fuel Values
    fuel_map: str | None = Field(default=None)
    active_fuel_map: FuelMap | None = Field(default=None)
    takeoff_fuel: int = Field(ge=0, default=0)
    reserve_fuel: int = Field(ge=0, default=0)
    rtb_altitude: int = Field(ge=0, default=14000)
    rtb_speed: int = Field(ge=0, default=420)
    # Consideration: WP Bookmark / Shorthand library

    @staticmethod
    def from_file(path: Path) -> 'Config':
        with path.open('r') as file:
            data = yaml.load(file, Loader=yaml.SafeLoader)
            overrides: list[ConfigOverride] = [ConfigOverride(**entry) for entry in data.pop('overrides')]
            conf = Config(**data, overrides=overrides)
            conf.load_fuel_map()
            return conf

    def override(self, override: str | None) -> 'Config':
        if override is not None:
            for override_opt in self.overrides:
                if override_opt.name == override:
                    return Config(
                        overview_card_downsample_factor=self.overview_card_downsample_factor,
                        route_colour=override_opt.route_colour or self.route_colour,
                        min_cruise_speed=override_opt.min_cruise_speed or self.min_cruise_speed,
                        default_cruise_speed=override_opt.default_cruise_speed or self.default_cruise_speed,
                        dash_speed=override_opt.dash_speed or self.dash_speed,
                        units=override_opt.units or self.units,
                    )
        return self

    def load_fuel_map(self):
        if self.fuel_map is not None:
            fuel_map_path = Path(f'../../fuel_maps/{self.fuel_map}.yaml')
            self.active_fuel_map = FuelMap.from_file(fuel_map_path)

if __name__ == '__main__':
    print(Config.from_file(Path('../../example_config.yaml')))
    print(Config.from_file(Path('../../example_config.yaml')).override('warbirds'))