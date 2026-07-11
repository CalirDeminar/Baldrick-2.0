from __future__ import annotations

from pydantic import BaseModel, Field

from domain.fuel_map import FuelMap
from shared.units import DistanceUnit

# Scalar fields that a named override is allowed to replace.
OVERRIDABLE_FIELDS = (
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

    def with_override(self, match: ConfigOverride) -> "Config":
        """Return a new Config with scalar fields replaced by the override."""
        values = {field: getattr(self, field) for field in OVERRIDABLE_FIELDS}
        for field in OVERRIDABLE_FIELDS:
            override_value = getattr(match, field)
            if override_value is not None:
                values[field] = override_value
        return Config(**values, overrides=self.overrides)
