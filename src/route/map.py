from pydantic import BaseModel
from pydantic import Field

class PixelMapPoint(BaseModel):
    lat_d: int = Field()
    lon_d: int = Field()
    x_pixel: int = Field()
    y_pixel: int = Field()

class Map(BaseModel):
    name: str = Field(frozen=True)
    pixel_map: dict[tuple[int, int], PixelMapPoint]
