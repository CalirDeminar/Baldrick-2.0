from __future__ import annotations

from enum import Enum
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from fuel.fuel_map import FuelMap
import paths


class DistanceUnit(Enum):
    NAUTICAL = "NAUTICAL"
    METRIC = "METRIC"
    IMPERIAL = "IMPERIAL"


# Scalar fields that a named override is allowed to replace.
_OVERRIDABLE_FIELDS = (
    "route_colour",
    "min_cruise_speed",
    "default_cruise_speed",
    "dash_speed",
    "units",
    "fuel_map",
    "takeoff_fuel",
    "reserve_fuel",
    "rtb_altitude",
    "rtb_speed",
    "overview_card_downsample_factor",
    "esa_safety_margin_ft",
)


class ConfigOverride(BaseModel):
    name: str = Field(min_length=1)
    route_colour: str | None = Field(default=None)
    min_cruise_speed: int | None = Field(default=None, ge=0)
    default_cruise_speed: int | None = Field(default=None, ge=0)
    dash_speed: int | None = Field(default=None, ge=0)
    units: DistanceUnit | None = Field(default=None)
    fuel_map: str | None = Field(default=None)
    takeoff_fuel: int | None = Field(default=None, ge=0)
    reserve_fuel: int | None = Field(default=None, ge=0)
    rtb_altitude: int | None = Field(default=None, ge=0)
    rtb_speed: int | None = Field(default=None, ge=0)
    overview_card_downsample_factor: float | None = Field(default=None, gt=0)
    esa_safety_margin_ft: int | None = Field(default=None, ge=0)


class Config(BaseModel):
    overview_card_downsample_factor: float = Field(gt=0, default=3)
    route_colour: str = Field(default="#000000")
    min_cruise_speed: int = Field(ge=0)
    default_cruise_speed: int = Field(ge=0)
    dash_speed: int = Field(ge=0)
    units: DistanceUnit = Field(default=DistanceUnit.NAUTICAL)
    overrides: list[ConfigOverride] = Field(default_factory=list)
    # Fuel values
    fuel_map: str | None = Field(default=None)
    active_fuel_map: FuelMap | None = Field(default=None)
    takeoff_fuel: int = Field(ge=0, default=0)
    reserve_fuel: int = Field(ge=0, default=0)
    rtb_altitude: int = Field(ge=0, default=14000)
    rtb_speed: int = Field(ge=0, default=420)
    # Emergency safe altitude margin (feet) added above the tallest obstacle.
    esa_safety_margin_ft: int = Field(ge=0, default=1000)

    @staticmethod
    def from_file(path: Path | None = None) -> "Config":
        path = path or paths.config_path()
        with path.open("r") as file:
            data = yaml.load(file, Loader=yaml.SafeLoader) or {}
        raw_overrides = data.pop("overrides", None) or []
        overrides = [ConfigOverride(**entry) for entry in raw_overrides]
        conf = Config(**data, overrides=overrides)
        conf.load_fuel_map()
        return conf

    def override(self, override: str | None) -> "Config":
        if override is None:
            return self
        match = next((o for o in self.overrides if o.name == override), None)
        if match is None:
            raise ValueError(
                f"Config override '{override}' not found. "
                f"Available: {[o.name for o in self.overrides] or 'none'}"
            )
        values = {field: getattr(self, field) for field in _OVERRIDABLE_FIELDS}
        for field in _OVERRIDABLE_FIELDS:
            override_value = getattr(match, field)
            if override_value is not None:
                values[field] = override_value
        result = Config(**values, overrides=self.overrides)
        result.load_fuel_map()
        return result

    def load_fuel_map(self) -> None:
        if self.fuel_map is not None:
            fuel_map_path = paths.fuel_maps_dir() / f"{self.fuel_map}.yaml"
            self.active_fuel_map = FuelMap.from_file(fuel_map_path)


if __name__ == "__main__":
    conf = Config.from_file()
    print(conf)
    print(conf.override("warbirds"))
