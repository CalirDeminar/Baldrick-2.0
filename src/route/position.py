from pydantic import BaseModel
from pydantic import Field

class DMSDistance(BaseModel):
    value: tuple[float, float, float] = Field()
    def to_decimal(self):
        return self.value[0] + (self.value[1] / 60) + (self.value[2] / 3600)
    @staticmethod
    def new(i: tuple[float, float, float]) -> 'DMSDistance':
        (d, m, s) = i
        return DMSDistance(value=(d, m, s))

class Position(BaseModel):
    latitude: DMSDistance = Field()
    longitude: DMSDistance = Field()

    def to_decimal(self):
        return self.latitude.to_decimal(), self.longitude.to_decimal()

    @staticmethod
    def new(latitude: tuple[float, float, float], longitude: tuple[float, float, float]) -> 'Position':
        return Position(latitude=(DMSDistance.new(latitude)), longitude=(DMSDistance.new(longitude)))


if __name__ == '__main__':
    test_position = Position.new(latitude=(12, 30, 0), longitude=(12, 30, 0))
    assert(test_position.to_decimal() == (12.5, 12.5))
