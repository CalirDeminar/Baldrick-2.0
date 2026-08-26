from __future__ import annotations

from datetime import timedelta

from pydantic import BaseModel, Field

from domain.config import Config
from domain.map import DCSMap
from domain.position import Position
from domain.turn_geometry import TurnArc
from shared.enums import Tag
from shared.units import DistanceUnit


def _segments_intersect(
    a1: tuple[float, float],
    a2: tuple[float, float],
    b1: tuple[float, float],
    b2: tuple[float, float],
) -> bool:
    """Return True if line segments a1-a2 and b1-b2 intersect (inclusive of endpoints)."""

    def ccw(p: tuple[float, float], q: tuple[float, float], r: tuple[float, float]) -> bool:
        return (q[1] - p[1]) * (r[0] - q[0]) > (q[0] - p[0]) * (r[1] - q[1])

    return (
        ccw(a1, b1, b2) != ccw(a2, b1, b2)
        and ccw(a1, a2, b1) != ccw(a1, a2, b2)
    )


class Waypoint(BaseModel):
    name: str = Field(min_length=1)
    position: Position
    tags: list[Tag] = Field(default_factory=list)
    timestamp: timedelta | None = Field(default=None)
    speed_to: int | None = Field(default=None, ge=0)
    altitude: int = Field(default=0, ge=0)
    notes: str | None = Field(default="")
    minimum_leg_alt: int | None = Field(default=None)
    min_fuel: int | None = Field(default=None)

    @property
    def is_fix(self) -> bool:
        return Tag.FIX in self.tags

    @property
    def is_ip(self) -> bool:
        return Tag.IP in self.tags

    @property
    def is_target(self) -> bool:
        return Tag.TGT in self.tags

    @property
    def is_divert(self) -> bool:
        return Tag.DIVERT in self.tags

    @property
    def is_aar(self) -> bool:
        return Tag.AAR in self.tags


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
    magvar: float | None = Field(default=None)
    bingo_fuel: int | None = Field(default=None)
    joker_fuel: int | None = Field(default=None)
    return_to_divert: bool | None = Field(default=None)
    flot: list[Position] = Field(default_factory=list)
    turn_arcs: list[TurnArc | None] | None = Field(default=None)

    @staticmethod
    def from_config(
        name: str,
        waypoints: list[Waypoint],
        conf: Config,
        flot: list[Position] | None = None,
        magvar: float | None = None,
    ) -> "Route":
        return Route(
            name=name,
            waypoints=waypoints,
            units=conf.units,
            dash_speed=conf.dash_speed,
            default_cruise_speed=conf.default_cruise_speed,
            min_cruise_speed=conf.min_cruise_speed,
            route_colour=conf.route_colour,
            flot=flot or [],
            magvar=magvar,
        )

    def leg_crosses_flot(self, a: Position, b: Position) -> bool:
        if len(self.flot) < 2:
            return False
        lat_a, lon_a = a.to_decimal()
        lat_b, lon_b = b.to_decimal()
        leg_start = (lon_a, lat_a)
        leg_end = (lon_b, lat_b)
        for i in range(len(self.flot) - 1):
            lat_1, lon_1 = self.flot[i].to_decimal()
            lat_2, lon_2 = self.flot[i + 1].to_decimal()
            flot_start = (lon_1, lat_1)
            flot_end = (lon_2, lat_2)
            if _segments_intersect(leg_start, leg_end, flot_start, flot_end):
                return True
        return False

    @property
    def push_waypoint(self) -> Waypoint | None:
        return next((wp for wp in self.waypoints if Tag.PUSH in wp.tags), None)

    @property
    def main_waypoints(self) -> list[Waypoint]:
        return [wp for wp in self.waypoints if Tag.DIVERT not in wp.tags]

    @property
    def divert_waypoints(self) -> list[Waypoint]:
        return [wp for wp in self.waypoints if Tag.DIVERT in wp.tags]

    @property
    def aar_waypoints(self) -> list[Waypoint]:
        return [wp for wp in self.main_waypoints if Tag.AAR in wp.tags]
