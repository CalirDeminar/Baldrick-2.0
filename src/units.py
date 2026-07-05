"""Unit handling.

The config's numeric speeds/distances are expressed in the active unit system
(nautical: kts/nm/ft, imperial: mph/mi/ft, metric: km-h/km/m). The fuel map is
always defined in kts / ft / lb-per-nm, so fuel calculations convert into those
canonical units first.
"""
from __future__ import annotations

from config.config import DistanceUnit

# 1 nautical mile in other distance units.
_NM_PER_KM = 1.0 / 1.852
_NM_PER_MILE = 1.0 / 1.150779448
_FT_PER_METRE = 3.280839895

DISTANCE_LABEL: dict[DistanceUnit, str] = {
    DistanceUnit.NAUTICAL: "nm",
    DistanceUnit.IMPERIAL: "mi",
    DistanceUnit.METRIC: "km",
}

SPEED_LABEL: dict[DistanceUnit, str] = {
    DistanceUnit.NAUTICAL: "kts",
    DistanceUnit.IMPERIAL: "mph",
    DistanceUnit.METRIC: "km/h",
}

ALTITUDE_LABEL: dict[DistanceUnit, str] = {
    DistanceUnit.NAUTICAL: "ft",
    DistanceUnit.IMPERIAL: "ft",
    DistanceUnit.METRIC: "m",
}


def distance_to_nm(value: float, units: DistanceUnit) -> float:
    if units == DistanceUnit.METRIC:
        return value * _NM_PER_KM
    if units == DistanceUnit.IMPERIAL:
        return value * _NM_PER_MILE
    return value


def speed_to_kts(value: float, units: DistanceUnit) -> float:
    # Speeds share the same ratio as their distance units (per hour).
    return distance_to_nm(value, units)


def altitude_to_ft(value: float, units: DistanceUnit) -> float:
    if units == DistanceUnit.METRIC:
        return value * _FT_PER_METRE
    return value


def altitude_from_ft(value_ft: float, units: DistanceUnit) -> float:
    if units == DistanceUnit.METRIC:
        return value_ft / _FT_PER_METRE
    return value_ft
