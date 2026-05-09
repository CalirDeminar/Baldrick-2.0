from datetime import timedelta
from pydantic import BaseModel
from pydantic import Field

from fuel.fuel import calculate_max_return_distance
from position import Position
from pathlib import Path
import yaml
import re
from questionary import ValidationError
from enums import Tag

from config.config import Config, DistanceUnit
from map import DCSMap



class RawWaypoint(BaseModel):
    name: str = Field(min_length=2)
    lat: str = Field(pattern=r"\d\d?\d?,\W?\d\d?,\W?\d\d?")
    long: str = Field(pattern=r"\d\d?\d?,\W?\d\d?,\W?\d\d?")
    tags: list[Tag] | None | None = Field(default=[])
    notes: str | None = Field(default=None)
    speed: str | None = Field(default=None)
    timestamp: str | None = Field(pattern=r"\d\d?\:\d\d?\:\d\d?", default=None)
    altitude: str = Field(default="0")


def parse_timestamp(timestamp_str: str) -> timedelta:
    if not re.match(r'\d{2}:\d{2}:\d{2}', timestamp_str):
        raise ValidationError(
            message=f"{timestamp_str} is not a valid timestamp",
        )
    [h, m, s] = timestamp_str.split(':')
    h_valid = 0 <= int(h) <= 24
    m_valid = 0 <= int(m) <= 59
    s_valid = 0 <= int(s) <= 59
    if h_valid and m_valid and s_valid:
        return timedelta(hours=int(h), minutes=int(m), seconds=int(s))
    raise ValidationError(message=f"{timestamp_str} is not a valid timestamp",)

class Waypoint(BaseModel):
    name: str = Field(min_length=1)
    timestamp: timedelta = Field()
    position: Position
    speed_to: int = Field(ge=0)
    notes: str | None = Field(default="")
    minimum_leg_alt: int | None = Field()
    planned_fuel: int | None = Field()
    altitude: int = Field(ge=0, default=0)

    tags: list[Tag] = Field()

    @staticmethod
    def from_dict(d: dict, conf: Config) -> 'Waypoint':
        raw_waypoint = RawWaypoint(**d)
        latitude = raw_waypoint.lat.split(', ')
        longitude = raw_waypoint.long.split(', ')
        latitude = (float(latitude[0]), float(latitude[1]), float(latitude[2]))
        longitude = (float(longitude[0]), float(longitude[1]), float(longitude[2]))
        position = Position.new(latitude=latitude, longitude=longitude)
        timestamp_str = raw_waypoint.timestamp
        timestamp = parse_timestamp(timestamp_str) if timestamp_str else timedelta()
        altitude = int(raw_waypoint.altitude)

        return Waypoint(
            name=d.get('name'),
            timestamp=timestamp,
            position=position,
            speed_to=raw_waypoint.speed if raw_waypoint.speed else conf.default_cruise_speed,
            notes=raw_waypoint.notes,
            minimum_leg_alt=None,
            planned_fuel=None,
            tags=raw_waypoint.tags,
            altitude=altitude
        )


class Route(BaseModel):
    name: str = Field(frozen=True, min_length=1)
    map: DCSMap = Field()
    start_time: timedelta = Field()
    time_on_target: timedelta = Field()
    dash_speed: int = Field(ge=0)
    default_cruise_speed: int = Field(ge=0)
    waypoints: list[Waypoint] = Field(min_length=1)
    units: DistanceUnit = Field()
    bingo_fuel: int | None = Field()
    bingo_divert: bool | None = Field()
    joker_fuel: int | None = Field()

    @staticmethod
    def new(path: Path, conf: Config) -> 'Route':
        with path.open('r') as file:
            data = yaml.load(file, Loader=yaml.SafeLoader)
            print(data)
            waypoints = [
                Waypoint.from_dict(waypoint_data, conf)
                for waypoint_data in data.get('waypoints')
            ] if data.get('waypoints') else []
            output = Route(
                name=data.get('name'),
                map=DCSMap.from_route_waypoints(waypoints),
                waypoints=waypoints,
                start_time=timedelta(0),
                time_on_target=timedelta(0),
                dash_speed=conf.dash_speed,
                default_cruise_speed=conf.default_cruise_speed,
                units=conf.units,
                bingo_fuel=None,
                joker_fuel=None,
                bingo_divert=None,
            )
            output.setup(config)
            return output


    def _setup_no_tot(self):
        prev_wp: Waypoint | None = None
        for wp in self.waypoints:
            if prev_wp:
                is_tgt = Tag.TGT in wp.tags
                if not wp.speed_to and is_tgt:
                    wp.speed_to = self.dash_speed
                distance_from_prev = wp.position.distance_from(prev_wp.position, self.units)
                time_from_prev = timedelta(hours=(distance_from_prev / wp.speed_to))
                time_total = prev_wp.timestamp + time_from_prev
                wp.timestamp = time_total

            prev_wp = wp

    def _setup_tot(self):
        timed_groups: list[list[Waypoint]] = []
        for wp in reversed(self.waypoints):
            if wp.timestamp.seconds != 0:
                timed_groups.append([wp])
            elif len(timed_groups) > 0:
                current_group = timed_groups[-1]
                current_group.append(wp)

        next_wp: Waypoint | None = None
        for i, group in enumerate(timed_groups):
            for j, wp in enumerate(group):
                if Tag.TGT in wp.tags:
                    wp.speed_to = self.dash_speed
                if next_wp:
                    distance = wp.position.distance_from(next_wp.position, self.units)
                    speed = self.default_cruise_speed
                    td = distance / speed
                    if next_wp.timestamp.seconds != 0 and wp.timestamp.seconds != 0:
                        td = round((next_wp.timestamp.seconds - wp.timestamp.seconds)/3600)
                        speed = round(distance / td)
                    wp.speed_to = speed
                    wp.timestamp = next_wp.timestamp - timedelta(seconds=round(td*3600))


                next_wp = wp

    def setup_fuel_cals(self, conf: Config):
        bingo_tag, max_return_distance_bingo = calculate_max_return_distance(self, is_bingo=True, conf=conf)
        rtb_fuel_efficiency = config.active_fuel_map.get_lb_per_mile_for_profile(altitude=conf.rtb_altitude, speed=conf.rtb_speed)
        self.bingo_fuel = int(max_return_distance_bingo * rtb_fuel_efficiency)
        self.bingo_divert = bingo_tag == Tag.DIVERT
        _, max_return_distance_joker = calculate_max_return_distance(self, conf=conf)
        self.joker_fuel = int(max_return_distance_joker * rtb_fuel_efficiency) + config.reserve_fuel
        required_fuel = config.reserve_fuel
        prev_wp = None
        for wp in reversed(self.waypoints):
            if Tag.HOME not in wp.tags and Tag.DIVERT not in wp.tags and prev_wp:
                leg_fuel_efficiency = config.active_fuel_map.get_lb_per_mile_for_profile(altitude=wp.altitude, speed=wp.speed_to)
                leg_length = prev_wp.position.distance_from(wp.position, self.units)
                leg_fuel = leg_length * leg_fuel_efficiency
                required_fuel += leg_fuel
                prev_wp.planned_fuel = int(required_fuel)
            if prev_wp and Tag.HOME in prev_wp.tags:
                prev_wp.planned_fuel = config.reserve_fuel
            prev_wp = wp
        required_fuel += config.takeoff_fuel
        if required_fuel > config.active_fuel_map.capacity:
            raise Exception("Route requires more fuel than current fuel capacity allows for")



    def setup(self, conf: Config) -> 'Route':
        # set up the ToT, define speeds, etc
            # One path for ToT defined
            # One path for ToT undefined (set to empty timedelta)
        has_tots = any([
            not (wp.timestamp.seconds == 0)
            for wp in self.waypoints
        ])
        if has_tots:
            self._setup_tot()
        else:
            self.setup_no_tot()
        self.setup_fuel_cals(conf)
        return self

if __name__ == '__main__':
    config = Config.from_file(Path('../../example_config.yaml'))
    route = Route.new(Path('../../example_route_file.yaml'), config)
    print(route)
    for wp in route.waypoints:
        print(wp)
