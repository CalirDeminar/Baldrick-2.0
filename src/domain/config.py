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
    "card_alpha",
    "faded_leg_alpha",
    "turn_g",
    "turn_rate_deg_per_sec",
)

# Override fields that may be explicitly cleared with null in YAML.
NULLABLE_OVERRIDE_FIELDS = frozenset({"fuel_map", "card_alpha"})


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
    card_alpha: int | None = Field(default=None, ge=0, le=255)
    faded_leg_alpha: int | None = Field(default=None, ge=0, le=255)
    turn_g: float | None = Field(default=None, gt=1.0)
    turn_rate_deg_per_sec: float | None = Field(default=None, gt=0)

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
    # Output card opacity (0=transparent, 255=opaque). Omit or null for fully opaque.
    card_alpha: int | None = Field(default=None, ge=0, le=255)
    # Opacity for non-current legs on leg cards (0=transparent, 255=opaque).
    faded_leg_alpha: int = Field(default=150, ge=0, le=255)
    # Coordinated turn load factor (must exceed 1G). Default 2G ≈ 60° bank.
    turn_g: float = Field(default=2.0, gt=1.0)
    # Optional radar/sensor turn-rate cap (deg/s). None = no limit.
    turn_rate_deg_per_sec: float | None = Field(default=None, gt=0)

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
            if field in NULLABLE_OVERRIDE_FIELDS and field in match.model_fields_set:
                values[field] = getattr(match, field)
                continue
            override_value = getattr(match, field)
            if override_value is not None:
                values[field] = override_value
        return Config(**values, overrides=self.overrides)


def effective_card_alpha(conf: Config) -> int:
    """Resolved output-card alpha: omitted or null means fully opaque (255)."""
    return 255 if conf.card_alpha is None else conf.card_alpha
