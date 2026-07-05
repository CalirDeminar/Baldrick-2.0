from __future__ import annotations

import re
from datetime import timedelta
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, model_validator

from config.config import Config, DistanceUnit
from enums import Tag
from routes.map import DCSMap
from routes.position import Position, parse_position


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


class Waypoint(BaseModel):
    name: str = Field(min_length=1)
    position: Position
    tags: list[Tag] = Field(default_factory=list)
    timestamp: timedelta | None = Field(default=None)
    speed_to: int | None = Field(default=None, ge=0)
    altitude: int = Field(default=0, ge=0)
    notes: str | None = Field(default="")
    minimum_leg_alt: int | None = Field(default=None)
    planned_fuel: int | None = Field(default=None)

    @property
    def is_fix(self) -> bool:
        return Tag.FIX in self.tags

    @property
    def is_ip(self) -> bool:
        return Tag.IP in self.tags

    @property
    def is_target(self) -> bool:
        return Tag.TGT in self.tags

    @staticmethod
    def from_dict(d: dict, conf: Config) -> "Waypoint":
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


class Route(BaseModel):
    name: str = Field(min_length=1)
    waypoints: list[Waypoint] = Field(min_length=1)
    units: DistanceUnit = Field()
    dash_speed: int = Field(ge=0)
    default_cruise_speed: int = Field(ge=0)
    min_cruise_speed: int = Field(ge=0)
    route_colour: str = Field(default="#000000")
    push_time: timedelta | None = Field(default=None)
    time_on_target: timedelta | None = Field(default=None)
    map_name: DCSMap | None = Field(default=None)
    bingo_fuel: int | None = Field(default=None)
    joker_fuel: int | None = Field(default=None)
    return_to_divert: bool | None = Field(default=None)

    @staticmethod
    def from_config(name: str, waypoints: list[Waypoint], conf: Config) -> "Route":
        return Route(
            name=name,
            waypoints=waypoints,
            units=conf.units,
            dash_speed=conf.dash_speed,
            default_cruise_speed=conf.default_cruise_speed,
            min_cruise_speed=conf.min_cruise_speed,
            route_colour=conf.route_colour,
        )

    @staticmethod
    def new(path: Path, conf: Config) -> "Route":
        with path.open("r") as file:
            data = yaml.load(file, Loader=yaml.SafeLoader) or {}
        raw_waypoints = data.get("waypoints") or []
        waypoints = [Waypoint.from_dict(wp, conf) for wp in raw_waypoints]
        return Route.from_config(name=data.get("name"), waypoints=waypoints, conf=conf)

    @property
    def push_waypoint(self) -> Waypoint | None:
        return next((wp for wp in self.waypoints if Tag.PUSH in wp.tags), None)
