from __future__ import annotations

import re
from datetime import timedelta

import questionary
from questionary import ValidationError, Validator

from config.config import Config
from enums import Tag
from routes.position import DMSDistance, Position
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


class _DMSValidator(Validator):
    max_degrees = 90

    def validate(self, document):
        parts = document.text.split(" ")
        if len(parts) != 3 or not all(p.lstrip("-").isdigit() for p in parts):
            raise ValidationError(message="Enter DMS as 'D M S', e.g. '49 26 30'")
        d, m, s = (float(p) for p in parts)
        if not -self.max_degrees <= d <= self.max_degrees:
            raise ValidationError(message=f"{d} is out of range for degrees")
        if not (0 <= m <= 60 and 0 <= s <= 60):
            raise ValidationError(message="Minutes and seconds must be between 0 and 60")


class DMSLatValidator(_DMSValidator):
    max_degrees = 90


class DMSLonValidator(_DMSValidator):
    max_degrees = 180


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
        lat = questionary.text(f"Waypoint[{idx}] Latitude (DMS 'D M S')", validate=DMSLatValidator).ask()
        lon = questionary.text(f"Waypoint[{idx}] Longitude (DMS 'D M S')", validate=DMSLonValidator).ask()

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
                position=Position(
                    latitude=DMSDistance.from_str(lat),
                    longitude=DMSDistance.from_str(lon),
                ),
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
