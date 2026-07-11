from __future__ import annotations

import math
import re
from typing import TYPE_CHECKING

import mgrs
from haversine import Unit, haversine
from pydantic import BaseModel, Field

from shared.units import DistanceUnit

haversine_unit: dict[DistanceUnit, Unit] = {
    DistanceUnit.NAUTICAL: Unit.NAUTICAL_MILES,
    DistanceUnit.IMPERIAL: Unit.MILES,
    DistanceUnit.METRIC: Unit.KILOMETERS,
}

if TYPE_CHECKING:
    from domain.route import Waypoint


class DMSDistance(BaseModel):
    value: tuple[float, float, float] = Field()

    def to_decimal(self) -> float:
        sign = -1 if self.value[0] < 0 else 1
        d, m, s = (abs(self.value[0]), self.value[1], self.value[2])
        return sign * (d + (m / 60) + (s / 3600))

    @staticmethod
    def new(i: tuple[float, float, float]) -> "DMSDistance":
        (d, m, s) = i
        return DMSDistance(value=(d, m, s))

    @staticmethod
    def from_decimal(decimal: float) -> "DMSDistance":
        sign = -1 if decimal < 0 else 1
        decimal = abs(decimal)
        degrees = int(decimal)
        remainder = (decimal - degrees) * 60
        minutes = int(remainder)
        seconds = (remainder - minutes) * 60
        return DMSDistance(value=(sign * degrees, minutes, seconds))

    def __repr__(self) -> str:
        return f"DMSDistance({self.value[0]}, {self.value[1]}, {self.value[2]})"


class Position(BaseModel):
    latitude: DMSDistance = Field()
    longitude: DMSDistance = Field()

    def to_decimal(self) -> tuple[float, float]:
        return self.latitude.to_decimal(), self.longitude.to_decimal()

    def distance_from(self, wp: "Position", units: DistanceUnit) -> float:
        return haversine(
            (self.latitude.to_decimal(), self.longitude.to_decimal()),
            (wp.latitude.to_decimal(), wp.longitude.to_decimal()),
            unit=haversine_unit[units],
        )

    def bearing_from(self, previous: "Position") -> float:
        """Initial true great-circle bearing (degrees) travelling from
        ``previous`` to ``self``, in the range [0, 360)."""
        own_lat = math.radians(self.latitude.to_decimal())
        own_long = math.radians(self.longitude.to_decimal())
        prev_lat = math.radians(previous.latitude.to_decimal())
        prev_long = math.radians(previous.longitude.to_decimal())

        d_long = own_long - prev_long
        x = math.cos(own_lat) * math.sin(d_long)
        y = math.cos(prev_lat) * math.sin(own_lat) - math.sin(prev_lat) * math.cos(own_lat) * math.cos(d_long)
        return (math.degrees(math.atan2(x, y)) + 360) % 360

    def __repr__(self) -> str:
        return f"Position({self.latitude}, {self.longitude})"

    def __hash__(self) -> int:
        return self.__repr__().__hash__()

    @staticmethod
    def new(
        latitude: tuple[float, float, float],
        longitude: tuple[float, float, float],
    ) -> "Position":
        return Position(
            latitude=DMSDistance.new(latitude),
            longitude=DMSDistance.new(longitude),
        )

    @staticmethod
    def from_decimal(latitude: float, longitude: float) -> "Position":
        return Position(
            latitude=DMSDistance.from_decimal(latitude),
            longitude=DMSDistance.from_decimal(longitude),
        )

    @staticmethod
    def from_mgrs(value: str) -> "Position":
        cleaned = re.sub(r"\s+", "", value.strip())
        try:
            lat, lon = mgrs.MGRS().toLatLon(cleaned)
        except Exception as exc:
            raise ValueError(f"'{value}' is not a valid MGRS coordinate") from exc
        return Position.from_decimal(lat, lon)
