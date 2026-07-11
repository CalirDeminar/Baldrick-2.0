from __future__ import annotations

import re
from datetime import timedelta
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, model_validator

from domain.config import Config
from domain.map import DCSMap
from domain.position import Position
from domain.route import Route, Waypoint
from parsing.coordinates import parse_position
from shared.enums import Tag
from shared.errors import BaldrickError


class RawWaypoint(BaseModel):
    name: str = Field(min_length=1)
    lat: str | None = Field(default=None)
    long: str | None = Field(default=None)
    mgrs: str | None = Field(default=None)
    tags: list[Tag] | None = Field(default_factory=list)
    notes: str | None = Field(default=None)
    speed: int | None = Field(default=None, ge=0)
    timestamp: str | None = Field(default=None, pattern=r"\d{1,2}:\d{1,2}:\d{1,2}")
    altitude: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_position_fields(self) -> "RawWaypoint":
        if self.mgrs:
            return self
        if self.lat and self.long:
            return self
        raise ValueError("Waypoint requires lat/long coordinates or an mgrs value")


def parse_timestamp(timestamp_str: str) -> timedelta:
    if not re.fullmatch(r"\d{1,2}:\d{1,2}:\d{1,2}", timestamp_str.strip()):
        raise ValueError(f"'{timestamp_str}' is not a valid HH:MM:SS timestamp")
    h, m, s = (int(part) for part in timestamp_str.strip().split(":"))
    if not (0 <= h <= 24 and 0 <= m <= 59 and 0 <= s <= 59):
        raise ValueError(f"'{timestamp_str}' is not a valid HH:MM:SS timestamp")
    return timedelta(hours=h, minutes=m, seconds=s)


def waypoint_from_dict(d: dict, conf: Config) -> Waypoint:
    raw = RawWaypoint(**d)
    position = parse_position(lat=raw.lat, lon=raw.long, mgrs_value=raw.mgrs)
    timestamp = parse_timestamp(raw.timestamp) if raw.timestamp else None
    return Waypoint(
        name=raw.name,
        position=position,
        tags=raw.tags or [],
        timestamp=timestamp,
        speed_to=raw.speed,
        altitude=raw.altitude,
        notes=raw.notes,
    )


def parse_flot(raw_flot: list[dict] | None) -> list[Position]:
    if not raw_flot:
        return []
    return [
        parse_position(
            lat=point.get("lat"),
            lon=point.get("long"),
            mgrs_value=point.get("mgrs"),
        )
        for point in raw_flot
    ]


def load_route(path: Path, conf: Config) -> Route:
    with path.open("r", encoding="utf-8") as file:
        data = yaml.load(file, Loader=yaml.SafeLoader) or {}
    raw_waypoints = data.get("waypoints") or []
    waypoints = [waypoint_from_dict(wp, conf) for wp in raw_waypoints]
    flot = parse_flot(data.get("flot"))
    route = Route.from_config(name=data.get("name"), waypoints=waypoints, conf=conf, flot=flot)

    raw_map = data.get("map")
    if raw_map is not None:
        map_name = DCSMap.from_name(str(raw_map))
        if map_name is None:
            raise BaldrickError(
                f"Unrecognised map '{raw_map}'. "
                f"Expected one of: {', '.join(m.value for m in DCSMap)}"
            )
        route.map_name = map_name

    return route
