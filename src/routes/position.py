import math
from pydantic import BaseModel
from pydantic import Field
from typing import TYPE_CHECKING
from config.config import DistanceUnit
from haversine import haversine, Unit

haversine_unit: dict[DistanceUnit, Unit] = {
    DistanceUnit.NAUTICAL: Unit.NAUTICAL_MILES,
    DistanceUnit.IMPERIAL: Unit.MILES,
    DistanceUnit.METRIC: Unit.KILOMETERS,
}

if TYPE_CHECKING:
    from routes.route import Waypoint

class DMSDistance(BaseModel):
    value: tuple[float, float, float] = Field()
    def to_decimal(self):
        return self.value[0] + (self.value[1] / 60) + (self.value[2] / 3600)
    @staticmethod
    def new(i: tuple[float, float, float]) -> 'DMSDistance':
        (d, m, s) = i
        return DMSDistance(value=(d, m, s))
    @staticmethod
    def from_str(i: str) -> 'DMSDistance':
        [d, m, s] = i.split(" ")
        [df, mf, sf] = [float(d), float(m), float(s)]
        return DMSDistance(value=(df, mf, sf))

    def __repr__(self):
        return f"DMSDistance({self.value[0]}, {self.value[1]}, {self.value[2]})"

class Position(BaseModel):
    latitude: DMSDistance = Field()
    longitude: DMSDistance = Field()

    def to_decimal(self):
        return self.latitude.to_decimal(), self.longitude.to_decimal()

    def distance_from(self, wp: 'Position', units: DistanceUnit) -> float:
        return haversine((self.latitude.to_decimal(), self.longitude.to_decimal()),(wp.latitude.to_decimal(), wp.longitude.to_decimal()), unit=haversine_unit[units])

    def bearing_from(self, previous: 'Position') -> float:
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

    def __repr__(self):
        return f"Position({self.latitude}, {self.longitude})"

    def __hash__(self):
        return self.__repr__().__hash__()

    @staticmethod
    def new(latitude: tuple[float, float, float], longitude: tuple[float, float, float]) -> 'Position':
        return Position(latitude=(DMSDistance.new(latitude)), longitude=(DMSDistance.new(longitude)))


if __name__ == '__main__':
    print(DMSDistance.from_str("1 1 1"))
    test_position = Position.new(latitude=(12, 30, 0), longitude=(12, 30, 0))
    assert(test_position.to_decimal() == (12.5, 12.5))
