from __future__ import annotations

import math
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

from domain.position import DMSDistance, Position
from shared import paths
from shared.errors import MapError

if TYPE_CHECKING:
    from domain.route import Waypoint


class DCSMap(Enum):
    CAUCASUS = "CAUCASUS"
    GERMANY = "GERMANY"
    NORMANDY = "NORMANDY"
    NTTR = "NTTR"
    PERSIAN_GULF = "PERSIAN_GULF"
    SYRIA = "SYRIA"

    @staticmethod
    def from_name(name: str) -> "DCSMap | None":
        try:
            return DCSMap(name.strip().upper())
        except ValueError:
            return None


class PixelMapPoint(BaseModel):
    position: Position = Field()
    x_pixel: int = Field()
    y_pixel: int = Field()


def _bucket_30(minutes: float) -> int:
    return 0 if minutes < 30 else 30


class MinAltMap(BaseModel):
    """Per-cell tallest-obstacle altitudes on a 30 arc-minute grid (feet)."""

    cells: dict[tuple[int, int, int, int], int] = Field(default_factory=dict)

    def min_alt_at(self, position: Position) -> int | None:
        lat = position.latitude.to_decimal()
        lon = position.longitude.to_decimal()
        key = (
            int(math.floor(lat)),
            _bucket_30((lat - math.floor(lat)) * 60),
            int(math.floor(lon)),
            _bucket_30((lon - math.floor(lon)) * 60),
        )
        return self.cells.get(key)

    def min_alt_between(self, a: Position, b: Position, samples: int = 64) -> int | None:
        lat_a, lon_a = a.to_decimal()
        lat_b, lon_b = b.to_decimal()
        highest: int | None = None
        for i in range(samples + 1):
            f = i / samples
            pos = Position.new(
                latitude=(lat_a + (lat_b - lat_a) * f, 0, 0),
                longitude=(lon_a + (lon_b - lon_a) * f, 0, 0),
            )
            alt = self.min_alt_at(pos)
            if alt is not None and (highest is None or alt > highest):
                highest = alt
        return highest


class MapLayer(BaseModel):
    """A single map image plus its lat/long -> pixel mapping.

    A layer is either a *base* map (its name matches a :class:`DCSMap`) or an
    *HD overlay* covering a smaller, higher-resolution sub-region.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str = Field()
    pixel_map: dict[Position, PixelMapPoint] = Field()
    projection_adjustment_deg: float = Field(default=0.0)
    mag_var: float = Field(default=0.0)
    layer_priority: int = Field(default=0)
    image_file: str = Field()
    min_alt: MinAltMap | None = Field(default=None)

    # ---- classification -------------------------------------------------
    @property
    def dcs_map(self) -> DCSMap | None:
        return DCSMap.from_name(self.name)

    @property
    def is_base(self) -> bool:
        return self.dcs_map is not None

    # ---- geometry -------------------------------------------------------
    @property
    def bounds(self) -> tuple[tuple[float, float], tuple[float, float]]:
        lats = [p.position.latitude.to_decimal() for p in self.pixel_map.values()]
        lons = [p.position.longitude.to_decimal() for p in self.pixel_map.values()]
        return (min(lats), max(lats)), (min(lons), max(lons))

    def point_within_map(self, position: "Position") -> bool:
        (min_lat, max_lat), (min_long, max_long) = self.bounds
        return (
            min_lat <= position.latitude.to_decimal() < max_lat
            and min_long <= position.longitude.to_decimal() < max_long
        )

    def waypoints_all_within_map(self, wps: list["Waypoint"]) -> bool:
        return all(self.point_within_map(wp.position) for wp in wps)

    def contains_bounds(self, other: "MapLayer") -> bool:
        (min_lat, max_lat), (min_long, max_long) = self.bounds
        (o_min_lat, o_max_lat), (o_min_long, o_max_long) = other.bounds
        return (
            min_lat <= o_min_lat and o_max_lat <= max_lat
            and min_long <= o_min_long and o_max_long <= max_long
        )

    def get_neighboring_pixels(
        self, position: Position
    ) -> tuple[PixelMapPoint, PixelMapPoint, PixelMapPoint, PixelMapPoint]:
        lat = position.latitude
        lon = position.longitude
        keys_by_lat = sorted(self.pixel_map.keys(), key=lambda p: p.latitude.to_decimal())
        keys_by_lon = sorted(self.pixel_map.keys(), key=lambda p: p.longitude.to_decimal())

        prev: Position | None = None
        active_lat: tuple[DMSDistance, DMSDistance] | None = None
        for k in keys_by_lat:
            if prev is not None and prev.latitude.to_decimal() != k.latitude.to_decimal():
                if prev.latitude.to_decimal() <= lat.to_decimal() <= k.latitude.to_decimal():
                    active_lat = prev.latitude, k.latitude
            prev = k

        prev = None
        active_lon: tuple[DMSDistance, DMSDistance] | None = None
        for k in keys_by_lon:
            if prev is not None and prev.longitude.to_decimal() != k.longitude.to_decimal():
                if prev.longitude.to_decimal() <= lon.to_decimal() <= k.longitude.to_decimal():
                    active_lon = prev.longitude, k.longitude
            prev = k

        if active_lat is None or active_lon is None:
            raise MapError(f"Position {position} is outside the pixel map for '{self.name}'")

        keys = (
            Position(latitude=active_lat[0], longitude=active_lon[0]),
            Position(latitude=active_lat[1], longitude=active_lon[0]),
            Position(latitude=active_lat[0], longitude=active_lon[1]),
            Position(latitude=active_lat[1], longitude=active_lon[1]),
        )
        return (
            self.pixel_map[keys[0]],
            self.pixel_map[keys[1]],
            self.pixel_map[keys[2]],
            self.pixel_map[keys[3]],
        )

    def get_pixels_for_position(self, position: Position) -> tuple[int, int]:
        lat = position.latitude.to_decimal()
        lon = position.longitude.to_decimal()

        for key, point in self.pixel_map.items():
            if key.latitude.to_decimal() == lat and key.longitude.to_decimal() == lon:
                return point.x_pixel, point.y_pixel

        sw, nw, se, ne = self.get_neighboring_pixels(position)
        lat_low = sw.position.latitude.to_decimal()
        lat_high = nw.position.latitude.to_decimal()
        lon_low = sw.position.longitude.to_decimal()
        lon_high = se.position.longitude.to_decimal()

        lat_low_factor = 1 - (lat - lat_low) / (lat_high - lat_low) if lat_high != lat_low else 1
        lon_low_factor = 1 - (lon - lon_low) / (lon_high - lon_low) if lon_high != lon_low else 1

        low_lon_x = (sw.x_pixel * lat_low_factor) + (nw.x_pixel * (1 - lat_low_factor))
        high_lon_x = (se.x_pixel * lat_low_factor) + (ne.x_pixel * (1 - lat_low_factor))
        x_pixel = (low_lon_x * lon_low_factor) + (high_lon_x * (1 - lon_low_factor))

        low_lon_y = (sw.y_pixel * lat_low_factor) + (nw.y_pixel * (1 - lat_low_factor))
        high_lon_y = (se.y_pixel * lat_low_factor) + (ne.y_pixel * (1 - lat_low_factor))
        y_pixel = (low_lon_y * lon_low_factor) + (high_lon_y * (1 - lon_low_factor))

        return round(x_pixel), round(y_pixel)

    def correspondence_to(self, base: "MapLayer") -> list[tuple[tuple[int, int], tuple[int, int]]]:
        """Pairs of (this layer pixel, base layer pixel) for shared grid points,
        used to fit an affine transform when compositing this layer onto base."""
        pairs: list[tuple[tuple[int, int], tuple[int, int]]] = []
        for point in self.pixel_map.values():
            if base.point_within_map(point.position):
                base_xy = base.get_pixels_for_position(point.position)
                pairs.append(((point.x_pixel, point.y_pixel), base_xy))
        return pairs

    def image_path(self) -> Path:
        return paths.map_image_dir() / self.image_file

    def load_image(self) -> Any:
        import pyvips

        return pyvips.Image.new_from_file(str(self.image_path()), access="random")


class MapSelection(BaseModel):
    """A chosen base map plus any HD overlays that apply to a route."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    base: MapLayer
    overlays: list[MapLayer] = Field(default_factory=list)

    @property
    def dcs_map(self) -> DCSMap | None:
        return self.base.dcs_map


class MapSet:
    """All map layers discovered under ``map_data``."""

    def __init__(self, layers: list[MapLayer]):
        self.layers = layers
        self.bases = [layer for layer in layers if layer.is_base]
        self.overlays = [layer for layer in layers if not layer.is_base]

    def overlays_for(self, base: MapLayer) -> list[MapLayer]:
        associated = [
            overlay for overlay in self.overlays if base.contains_bounds(overlay)
        ]
        return sorted(associated, key=lambda layer: layer.layer_priority)

    def select_for(self, waypoints: list["Waypoint"]) -> MapSelection:
        base = next(
            (b for b in self.bases if b.waypoints_all_within_map(waypoints)), None
        )
        if base is None:
            raise MapError(self._out_of_bounds_report(waypoints))
        return MapSelection(base=base, overlays=self.overlays_for(base))

    def _out_of_bounds_report(self, waypoints: list["Waypoint"]) -> str:
        lines = ["No supported map fully contains this route."]
        if not self.bases:
            lines.append("No base maps were found in the map_data folder.")
        for base in self.bases:
            outside = [wp.name for wp in waypoints if not base.point_within_map(wp.position)]
            if outside:
                lines.append(f"  {base.name}: waypoints out of bounds: {', '.join(outside)}")
            else:
                lines.append(f"  {base.name}: contains all waypoints")
        return "\n".join(lines)
