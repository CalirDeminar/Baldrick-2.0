from __future__ import annotations

import re
from datetime import timedelta

import questionary
from questionary import ValidationError, Validator

from config.config import Config
from enums import Tag
from routes.position import parse_coordinate, parse_position
from routes.route import Route, Waypoint, parse_timestamp


class IntegerValidator(Validator):
    def validate(self, document):
        if not document.text.isdigit():
            raise ValidationError(
                message=f"{document.text} is not a valid integer",
                cursor_position=len(document.text),
            )


class TimestampValidator(Validator):
    def validate(self, document):
        if not re.match(r"\d{1,2}:\d{1,2}:\d{1,2}", document.text):
            raise ValidationError(
                message=f"{document.text} is not a valid HH:MM:SS timestamp",
                cursor_position=len(document.text),
            )


class _CoordinateValidator(Validator):
    axis = "lat"
    max_degrees = 90

    def validate(self, document):
        try:
            parsed = parse_coordinate(document.text, kind=self.axis)
        except ValueError as exc:
            raise ValidationError(
                message=str(exc),
                cursor_position=len(document.text),
            ) from exc
        if abs(parsed.to_decimal()) > self.max_degrees:
            raise ValidationError(
                message=f"Value is out of range for {self.axis}",
                cursor_position=len(document.text),
            )


class LatCoordinateValidator(_CoordinateValidator):
    axis = "lat"
    max_degrees = 90


class LonCoordinateValidator(_CoordinateValidator):
    axis = "lon"
    max_degrees = 180


class MGRSValidator(Validator):
    def validate(self, document):
        try:
            parse_position(mgrs_value=document.text)
        except ValueError as exc:
            raise ValidationError(
                message=str(exc),
                cursor_position=len(document.text),
            ) from exc


def _ask_position(idx: int):
    use_mgrs = questionary.confirm(
        f"Waypoint[{idx}] enter position as MGRS?", default=False
    ).ask()
    if use_mgrs:
        mgrs_value = questionary.text(
            f"Waypoint[{idx}] MGRS coordinate",
            validate=MGRSValidator,
        ).ask()
        return parse_position(mgrs_value=mgrs_value)

    lat = questionary.text(
        f"Waypoint[{idx}] Latitude (DMS 'D M S' or DDM 'D MM.M')",
        validate=LatCoordinateValidator,
    ).ask()
    lon = questionary.text(
        f"Waypoint[{idx}] Longitude (DMS 'D M S' or DDM 'D MM.M')",
        validate=LonCoordinateValidator,
    ).ask()
    return parse_position(lat=lat, lon=lon)


def build_route_interactive(conf: Config) -> Route:
    route_name = questionary.text("Route Name").ask()
    waypoints: list[Waypoint] = []
    tag_choices = [t.value for t in Tag]

    adding = True
    while adding:
        idx = len(waypoints) + 1
        name = questionary.text(f"Waypoint[{idx}] Name").ask()
        raw_tags = questionary.checkbox(
            f"Waypoint[{idx}] tags:", choices=tag_choices
        ).ask() or []
        position = _ask_position(idx)

        speed: int | None = None
        timestamp: timedelta | None = None
        altitude = 0
        if waypoints:
            if questionary.confirm(f"Waypoint[{idx}] has a specific leg speed?", default=False).ask():
                speed = int(questionary.text(f"Waypoint[{idx}] Speed", validate=IntegerValidator).ask())
            if questionary.confirm(f"Waypoint[{idx}] has a specific altitude?", default=False).ask():
                altitude = int(questionary.text(f"Waypoint[{idx}] Altitude", validate=IntegerValidator).ask())
            if questionary.confirm(f"Waypoint[{idx}] has a fixed time (ToT)?", default=False).ask():
                timestamp = parse_timestamp(
                    questionary.text("Time (HH:MM:SS)", validate=TimestampValidator).ask()
                )
        notes = questionary.text(f"Waypoint[{idx}] Notes (optional)").ask()

        waypoints.append(
            Waypoint(
                name=name,
                position=position,
                tags=[Tag(t) for t in raw_tags],
                speed_to=speed,
                timestamp=timestamp,
                altitude=altitude,
                notes=notes or "",
            )
        )
        if len(waypoints) >= 1:
            adding = questionary.confirm("Add another waypoint?", default=True).ask()

    return Route.from_config(name=route_name, waypoints=waypoints, conf=conf)
