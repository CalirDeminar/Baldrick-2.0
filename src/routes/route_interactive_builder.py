from config.config import Config
from routes.route import Route, Waypoint, Tag, DCSMap, parse_timestamp

import questionary
from pathlib import Path
from questionary import Validator, ValidationError
from datetime import timedelta
from routes.position import Position, DMSDistance
import re


class IntegerValidator(Validator):
    def validate(self, document):
        if not document.text.isdigit():
            raise ValidationError(
                message=f"{document.text} is not a valid integer",
                cursor_position=len(document.text)
            )

class TimestampValidator(Validator):
    def validate(self, document):
        if not re.match(r'\d{2}:\d{2}:\d{2}', document.text):
            raise ValidationError(
                message=f"{document.text} is not a valid timestamp",
                cursor_position=len(document.text)
            )

class DMSLatValidator(Validator):
    def validate(self, document):
        if not document.text.count(" ") == 2:
            raise ValidationError(
                message=f"{document.text} is not a valid DMS. Needs H M S components",
            )
        [d, m, s] = document.text.split(" ")
        if not (d.isdigit() and m.isdigit() and s.isdigit()):
            raise ValidationError(
                message=f"{document.text} is not a valid DMS. H, M and S components must all be digits",
            )
        [df, mf, sf] = [float(d), float(m), float(s)]
        if not -90 <= df <= 90:
            raise ValidationError(
                message=f"{df} is not a valid DMS degree component"
            )
        if not 0 <= mf <= 60:
            raise ValidationError(
                message=f"{df} is not a valid DMS minute component"
            )
        if not 0 <= sf <= 60:
            raise ValidationError(
                message=f"{df} is not a valid DMS seconds component"
            )
class DMSLonValidator(Validator):
    def validate(self, document):
        if not document.text.count(" ") == 2:
            raise ValidationError(
                message=f"{document.text} is not a valid DMS. Needs H M S components",
            )
        [d, m, s] = document.text.split(" ")
        if not (d.isdigit() and m.isdigit() and s.isdigit()):
            raise ValidationError(
                message=f"{document.text} is not a valid DMS. H, M and S components must all be digits",
            )
        [df, mf, sf] = [float(d), float(m), float(s)]
        if not -180 <= df <= 180:
            raise ValidationError(
                message=f"{df} is not a valid DMS degree component"
            )
        if not 0 <= mf <= 60:
            raise ValidationError(
                message=f"{df} is not a valid DMS minute component"
            )
        if not 0 <= sf <= 60:
            raise ValidationError(
                message=f"{df} is not a valid DMS seconds component"
            )


def build_route_interactive(conf: Config):
    route_name = questionary.text("Route Name").ask()
    has_next_wp: bool = True
    # Add config
    wps: list[Waypoint] = []
    tot: timedelta = timedelta()
    while has_next_wp:
        wp_name = questionary.text(f"Waypoint[{len(wps) + 1}] Name").ask()
        tag_inputs: list[str] = [Tag.TGT.value, Tag.IP.value, Tag.FIX.value, Tag.PUSH.value, Tag.HOME.value, Tag.DIVERT.value]
        wp_tags_raw = questionary.checkbox(f"[{len(wps) + 1}] What type of Waypoint is this:", choices=tag_inputs).ask()
        wp_lat = questionary.text(f"Waypoint[{len(wps) + 1}] Latitude (DMS) Degrees", validate=DMSLatValidator).ask()
        wp_lon = questionary.text(f"Waypoint[{len(wps) + 1}] Latitude (DMS) Degrees", validate=DMSLonValidator).ask()
        wp_speed: int  = 0
        local_tot: timedelta = timedelta()
        if len(wps) > 0:
            has_speed = questionary.confirm(f"Waypoint[{len(wps) + 1}] has specific Speed", default=False).ask()
            if has_speed:
                wp_speed = int(questionary.text(f"Waypoint[{len(wps) + 1}] Speed", validate=IntegerValidator).ask())
            if Tag.TGT.value in wp_tags_raw:
                tgt_tot_raw = questionary.text("Time on Target", validate=TimestampValidator).ask()
                local_tot = parse_timestamp(tgt_tot_raw)
                tot = local_tot
        notes = questionary.text(f"Waypoint[{len(wps) + 1}] Notes").ask()
        to_add = Waypoint(
            name=wp_name,
            tags=wp_tags_raw,
            speed_to=wp_speed,
            timestamp=local_tot,
            position=Position(
                latitude=DMSDistance.from_str(wp_lat),
                longitude=DMSDistance.from_str(wp_lon),
            ),
            notes=notes,
            minimum_leg_alt=None,
        )
        wps.append(to_add)
        if len(wps) > 1:
            has_next_wp = questionary.confirm("Is there another waypoint?", default=True).ask()
    return Route(
        waypoints=wps,
        name=route_name,
        time_on_target=tot,
        start_time=timedelta(),
        dash_speed=conf.dash_speed,
        default_cruise_speed=conf.default_cruise_speed,
        map=DCSMap.from_route_waypoints(wps),
        units=conf.units,
    )

if __name__ == '__main__':
    config = Config.from_file(Path('../example_config.yaml'))
    build_route_interactive(config)