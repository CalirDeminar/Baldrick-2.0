from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field


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
    def from_file(path: Path) -> "FuelMap":
        with path.open("r") as f:
            data = yaml.load(f, Loader=yaml.SafeLoader)
        fuel_map_by_altitude: dict[int, FuelMapBySpeed] = {}
        for row in data.get("fuelMap"):
            altitude_ft = int(row["altitude_ft"])
            speed_kts = int(row["speed_kts"])
            lb_per_nm = float(row["lb_per_nm"])
            if altitude_ft not in fuel_map_by_altitude:
                fuel_map_by_altitude[altitude_ft] = FuelMapBySpeed(
                    altitude=altitude_ft, map_by_speed={}
                )
            fuel_map_by_altitude[altitude_ft].map_by_speed[speed_kts] = FuelMapCell(
                speed_kts=speed_kts,
                altitude_ft=altitude_ft,
                fuel_lbs_per_nm=lb_per_nm,
            )
        capacity = int(str(data["capacity"]).replace(",", ""))
        return FuelMap(
            fuel_map_by_altitude=fuel_map_by_altitude,
            name=data["name"],
            capacity=capacity,
        )

    @property
    def altitudes(self) -> list[int]:
        return sorted(self.fuel_map_by_altitude.keys())

    @property
    def speeds(self) -> list[int]:
        speeds: set[int] = set()
        for alt in self.fuel_map_by_altitude.values():
            speeds.update(alt.map_by_speed.keys())
        return sorted(speeds)

    @property
    def altitude_bounds(self) -> tuple[int, int]:
        alts = self.altitudes
        return alts[0], alts[-1]

    @property
    def speed_bounds(self) -> tuple[int, int]:
        speeds = self.speeds
        return speeds[0], speeds[-1]

    def is_within_bounds(self, altitude_ft: float, speed_kts: float) -> bool:
        (alt_min, alt_max) = self.altitude_bounds
        (spd_min, spd_max) = self.speed_bounds
        return alt_min <= altitude_ft <= alt_max and spd_min <= speed_kts <= spd_max

    def bounds_description(self) -> str:
        (alt_min, alt_max) = self.altitude_bounds
        (spd_min, spd_max) = self.speed_bounds
        return (
            f"altitude {alt_min}-{alt_max}ft, speed {spd_min}-{spd_max}kts"
        )

    def _clamp(self, altitude_ft: float, speed_kts: float) -> tuple[float, float]:
        (alt_min, alt_max) = self.altitude_bounds
        (spd_min, spd_max) = self.speed_bounds
        return (
            min(max(altitude_ft, alt_min), alt_max),
            min(max(speed_kts, spd_min), spd_max),
        )

    def get_profile_key_neighbors(
        self, altitude: float, speed: float
    ) -> tuple[int, int, int, int]:
        altitudes = self.altitudes
        speeds = self.speeds
        altitudes_below = [a for a in altitudes if a <= altitude]
        altitudes_above = [a for a in altitudes if a >= altitude]
        speeds_below = [s for s in speeds if s <= speed]
        speeds_above = [s for s in speeds if s >= speed]
        altitude_low = altitudes_below[-1]
        altitude_high = altitudes_above[0]
        speed_low = speeds_below[-1]
        speed_high = speeds_above[0]
        return altitude_low, altitude_high, speed_low, speed_high

    def get_lb_per_mile_for_profile(self, altitude: float, speed: float) -> float:
        """2D linear interpolation of consumption for a speed/altitude profile.

        Values outside the mapped bounds are clamped to the nearest edge (the
        caller is expected to warn about the out-of-bounds regime separately).
        """
        (altitude, speed) = self._clamp(altitude, speed)
        (altitude_low, altitude_high, speed_low, speed_high) = (
            self.get_profile_key_neighbors(altitude, speed)
        )

        low_speed_low_altitude = self.fuel_map_by_altitude[altitude_low].map_by_speed[speed_low].fuel_lbs_per_nm
        low_speed_high_altitude = self.fuel_map_by_altitude[altitude_high].map_by_speed[speed_low].fuel_lbs_per_nm
        high_speed_low_altitude = self.fuel_map_by_altitude[altitude_low].map_by_speed[speed_high].fuel_lbs_per_nm
        high_speed_high_altitude = self.fuel_map_by_altitude[altitude_high].map_by_speed[speed_high].fuel_lbs_per_nm

        altitude_low_factor = (
            1 - (altitude - altitude_low) / (altitude_high - altitude_low)
            if (altitude_high - altitude_low) != 0
            else 1
        )
        speed_low_factor = (
            1 - (speed - speed_low) / (speed_high - speed_low)
            if (speed_high - speed_low) != 0
            else 1
        )

        low_speed_figure = (low_speed_low_altitude * altitude_low_factor) + (
            low_speed_high_altitude * (1 - altitude_low_factor)
        )
        high_speed_figure = (high_speed_low_altitude * altitude_low_factor) + (
            high_speed_high_altitude * (1 - altitude_low_factor)
        )

        return (low_speed_figure * speed_low_factor) + (
            high_speed_figure * (1 - speed_low_factor)
        )
