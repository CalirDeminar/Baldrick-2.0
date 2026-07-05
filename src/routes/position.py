from __future__ import annotations

import math
import re
from typing import TYPE_CHECKING, Literal

import mgrs
from haversine import Unit, haversine
from pydantic import BaseModel, Field

from config.config import DistanceUnit

haversine_unit: dict[DistanceUnit, Unit] = {
    DistanceUnit.NAUTICAL: Unit.NAUTICAL_MILES,
    DistanceUnit.IMPERIAL: Unit.MILES,
    DistanceUnit.METRIC: Unit.KILOMETERS,
}

if TYPE_CHECKING:
    from routes.route import Waypoint

_DMS_COMMA = re.compile(
    r"^\s*(-?\d{1,3})\s*,\s*(\d{1,2}(?:\.\d+)?)\s*,\s*(\d{1,2}(?:\.\d+)?)\s*$"
)
_DMS_SPACE = re.compile(
    r"^\s*(-?\d{1,3})\s+(\d{1,2}(?:\.\d+)?)\s+(\d{1,2}(?:\.\d+)?)\s*$"
)
_DDM = re.compile(
    r"^\s*([NSWE])?\s*(-?\d{1,3}(?:\.\d+)?)\s+(\d{1,2}(?:\.\d+)?)\s*([NSWE])?\s*$",
    re.IGNORECASE,
)
_MGRS = re.compile(
    r"^\s*\d{1,2}[C-HJ-NP-Xc-hj-np-x]\s*[A-HJ-NP-Za-hj-np-z]{2}\s*\d+\s*\d+\s*$"
)


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
    def from_str(i: str) -> "DMSDistance":
        return parse_coordinate(i, kind="lat")

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


def _looks_like_mgrs(value: str) -> bool:
    return bool(_MGRS.match(value.strip()))


def _parse_dms(value: str) -> DMSDistance:
    text = value.strip()
    match = _DMS_COMMA.match(text) or _DMS_SPACE.match(text)
    if not match:
        raise ValueError(f"'{value}' is not a valid DMS coordinate")
    degrees, minutes, seconds = (float(part) for part in match.groups())
    if not (0 <= minutes < 60 and 0 <= seconds < 60):
        raise ValueError(f"'{value}' has minutes or seconds out of range")
    return DMSDistance.new((degrees, minutes, seconds))


def _parse_ddm(value: str, *, kind: Literal["lat", "lon"]) -> DMSDistance:
    text = value.strip()
    match = _DDM.match(text)
    if not match:
        raise ValueError(f"'{value}' is not a valid DDM coordinate")

    prefix, degrees_raw, minutes_raw, suffix = match.groups()
    degrees = float(degrees_raw)
    minutes = float(minutes_raw)
    if not (0 <= minutes < 60):
        raise ValueError(f"'{value}' has decimal minutes out of range")

    hemisphere = (prefix or suffix or "").upper()
    if hemisphere in {"N", "S"} and kind != "lat":
        raise ValueError(f"'{value}' uses a latitude hemisphere on a longitude field")
    if hemisphere in {"E", "W"} and kind != "lon":
        raise ValueError(f"'{value}' uses a longitude hemisphere on a latitude field")

    if hemisphere in {"S", "W"}:
        sign = -1
    elif hemisphere in {"N", "E"}:
        sign = 1
    elif degrees < 0:
        sign = -1
    else:
        sign = 1

    decimal = sign * (abs(degrees) + (minutes / 60))
    max_degrees = 90 if kind == "lat" else 180
    if abs(decimal) > max_degrees:
        raise ValueError(f"'{value}' is out of range for {kind}")
    return DMSDistance.from_decimal(decimal)


def parse_coordinate(value: str, *, kind: Literal["lat", "lon"]) -> DMSDistance:
    text = value.strip()
    if _looks_like_mgrs(text):
        raise ValueError(
            f"'{value}' looks like an MGRS grid reference; use the 'mgrs' field instead"
        )
    if _DMS_COMMA.match(text) or _DMS_SPACE.match(text):
        parsed = _parse_dms(text)
    elif _DDM.match(text):
        parsed = _parse_ddm(text, kind=kind)
    else:
        raise ValueError(f"'{value}' is not a valid DMS or DDM coordinate")

    max_degrees = 90 if kind == "lat" else 180
    if abs(parsed.to_decimal()) > max_degrees:
        raise ValueError(f"'{value}' is out of range for {kind}")
    return parsed


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


def parse_position(
    lat: str | None = None,
    lon: str | None = None,
    mgrs_value: str | None = None,
) -> Position:
    if mgrs_value:
        return Position.from_mgrs(mgrs_value)
    if lat and _looks_like_mgrs(lat):
        return Position.from_mgrs(lat)
    if not lat or not lon:
        raise ValueError("Waypoint requires lat/long coordinates or an mgrs value")
    return Position(
        latitude=parse_coordinate(lat, kind="lat"),
        longitude=parse_coordinate(lon, kind="lon"),
    )


if __name__ == "__main__":
    print(DMSDistance.from_str("1 1 1"))
    test_position = Position.new(latitude=(12, 30, 0), longitude=(12, 30, 0))
    assert test_position.to_decimal() == (12.5, 12.5)
