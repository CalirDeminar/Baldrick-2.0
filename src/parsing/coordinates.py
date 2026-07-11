from __future__ import annotations

import re
from typing import Literal

from domain.position import DMSDistance, Position

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
