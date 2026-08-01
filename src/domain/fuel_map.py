from __future__ import annotations

from pydantic import BaseModel, Field

from shared.errors import FuelMapError


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

    def speed_bounds_at_altitude(self, altitude_ft: int) -> tuple[int, int]:
        speeds = sorted(self.fuel_map_by_altitude[altitude_ft].map_by_speed.keys())
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

    def profile_approximation_notes(
        self, altitude_ft: float, speed_kts: float
    ) -> list[str]:
        """Reasons a profile may be approximated beyond the global bounds check."""
        notes: list[str] = []
        (altitude_ft, speed_kts) = self._clamp(altitude_ft, speed_kts)
        altitude_low, altitude_high = self._altitude_neighbors(altitude_ft)
        for altitude in dict.fromkeys((altitude_low, altitude_high)):
            speed_min, speed_max = self.speed_bounds_at_altitude(altitude)
            if speed_kts > speed_max:
                notes.append(
                    f"speed {speed_kts:.0f} kts exceeds the {speed_max} kts maximum "
                    f"recorded at {altitude:,} ft"
                )
            elif speed_kts < speed_min:
                notes.append(
                    f"speed {speed_kts:.0f} kts is below the {speed_min} kts minimum "
                    f"recorded at {altitude:,} ft"
                )
        return notes

    def _clamp(self, altitude_ft: float, speed_kts: float) -> tuple[float, float]:
        (alt_min, alt_max) = self.altitude_bounds
        (spd_min, spd_max) = self.speed_bounds
        return (
            min(max(altitude_ft, alt_min), alt_max),
            min(max(speed_kts, spd_min), spd_max),
        )

    def _altitude_neighbors(self, altitude: float) -> tuple[int, int]:
        altitudes = self.altitudes
        altitudes_below = [a for a in altitudes if a <= altitude]
        altitudes_above = [a for a in altitudes if a >= altitude]
        return altitudes_below[-1], altitudes_above[0]

    def _speed_neighbors_at_altitude(
        self, altitude_ft: int, speed: float
    ) -> tuple[int, int]:
        speeds = sorted(self.fuel_map_by_altitude[altitude_ft].map_by_speed.keys())
        speeds_below = [s for s in speeds if s <= speed]
        speeds_above = [s for s in speeds if s >= speed]
        speed_low = speeds_below[-1] if speeds_below else speeds[0]
        speed_high = speeds_above[0] if speeds_above else speeds[-1]
        return speed_low, speed_high

    def _cell_value(self, altitude_ft: int, speed_kts: int) -> float:
        try:
            return self.fuel_map_by_altitude[altitude_ft].map_by_speed[
                speed_kts
            ].fuel_lbs_per_nm
        except KeyError as exc:
            available = sorted(
                self.fuel_map_by_altitude[altitude_ft].map_by_speed.keys()
            )
            raise FuelMapError(
                f"Fuel map '{self.name}' has no data for {speed_kts} kts at "
                f"{altitude_ft:,} ft (available speeds: "
                f"{', '.join(str(s) for s in available)} kts)."
            ) from exc

    def _value_at_altitude(self, altitude_ft: int, speed: float) -> float:
        speed_low, speed_high = self._speed_neighbors_at_altitude(altitude_ft, speed)
        value_low = self._cell_value(altitude_ft, speed_low)
        if speed_low == speed_high:
            return value_low
        speed_factor = (speed - speed_low) / (speed_high - speed_low)
        value_high = self._cell_value(altitude_ft, speed_high)
        return (value_low * (1 - speed_factor)) + (value_high * speed_factor)

    def get_profile_key_neighbors(
        self, altitude: float, speed: float
    ) -> tuple[int, int, int, int]:
        altitude_low, altitude_high = self._altitude_neighbors(altitude)
        speed_low, speed_high = self._speed_neighbors_at_altitude(
            altitude_low, speed
        )
        return altitude_low, altitude_high, speed_low, speed_high

    def get_lb_per_mile_for_profile(self, altitude: float, speed: float) -> float:
        """Interpolate consumption for a speed/altitude profile.

        Speed is interpolated within each altitude band using only the speeds
        recorded for that band, then altitude is interpolated between bands.
        This supports maps where higher altitudes have fewer achievable speeds.

        Values outside the mapped global bounds are clamped to the nearest edge
        (the caller is expected to warn about approximation separately).
        """
        (altitude, speed) = self._clamp(altitude, speed)
        altitude_low, altitude_high = self._altitude_neighbors(altitude)
        value_low = self._value_at_altitude(altitude_low, speed)
        if altitude_low == altitude_high:
            return value_low
        altitude_factor = (altitude - altitude_low) / (altitude_high - altitude_low)
        value_high = self._value_at_altitude(altitude_high, speed)
        return (value_low * (1 - altitude_factor)) + (value_high * altitude_factor)
