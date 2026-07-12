from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

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


def _blank_str_to_none(value: Any) -> Any:
    """Treat omitted/blank fuel map names as opting out of fuel planning."""
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    return value


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

    @field_validator("fuel_map", mode="before")
    @classmethod
    def normalize_fuel_map(cls, value: Any) -> Any:
        return _blank_str_to_none(value)


class Config(BaseModel):
    overview_card_downsample_factor: float = Field(gt=0, default=3)
    route_colour: str = Field(default="#000000")
    min_cruise_speed: int = Field(ge=0)
    default_cruise_speed: int = Field(ge=0)
    dash_speed: int = Field(ge=0)
    units: DistanceUnit = Field(default=DistanceUnit.NAUTICAL)
    overrides: list[ConfigOverride] = Field(default_factory=list)
    # Fuel values — omit or set null/blank to skip fuel calculations.
    fuel_map: str | None = Field(default=None)
    active_fuel_map: FuelMap | None = Field(default=None)
    takeoff_fuel: int = Field(ge=0, default=0)
    reserve_fuel: int = Field(ge=0, default=0)
    rtb_altitude: int = Field(ge=0, default=14000)
    rtb_speed: int = Field(ge=0, default=420)
    # Emergency safe altitude margin (feet) added above the tallest obstacle.
    esa_safety_margin_ft: int = Field(ge=0, default=1000)

    @field_validator("fuel_map", mode="before")
    @classmethod
    def normalize_fuel_map(cls, value: Any) -> Any:
        return _blank_str_to_none(value)

    def with_override(self, match: ConfigOverride) -> "Config":
        """Return a new Config with scalar fields replaced by the override.

        Non-null override values replace the base. ``fuel_map`` may also be
        cleared explicitly with ``fuel_map: null`` (or blank) in the override.
        """
        values = {field: getattr(self, field) for field in OVERRIDABLE_FIELDS}
        for field in OVERRIDABLE_FIELDS:
            if field == "fuel_map" and field in match.model_fields_set:
                values[field] = getattr(match, field)
                continue
            override_value = getattr(match, field)
            if override_value is not None:
                values[field] = override_value
        return Config(**values, overrides=self.overrides)
