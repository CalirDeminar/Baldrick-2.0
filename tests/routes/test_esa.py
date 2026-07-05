from config.config import Config, DistanceUnit
from routes.esa import compute_esa
from routes.map import MapLayer, MapSelection, MinAltMap, PixelMapPoint
from routes.position import Position
from routes.route import Route, Waypoint


def _layer_with_min_alt() -> MapLayer:
    pixel_map = {}
    for lat in (49, 50, 51):
        for lon in (10, 11, 12):
            pos = Position.new((lat, 0, 0), (lon, 0, 0))
            pixel_map[pos] = PixelMapPoint(position=pos, x_pixel=lat, y_pixel=lon)
    min_alt = MinAltMap.from_rows(
        [
            {"lat": "50, 0, 0", "long": "10, 0, 0", "altitude_ft": 3200},
            {"lat": "50, 0, 0", "long": "11, 0, 0", "altitude_ft": 1500},
        ]
    )
    return MapLayer(name="GERMANY", pixel_map=pixel_map, image_file="GERMANY.jpg", min_alt=min_alt)


def test_esa_uses_highest_obstacle_plus_margin():
    conf = Config(min_cruise_speed=300, default_cruise_speed=420, dash_speed=540,
                  units=DistanceUnit.NAUTICAL, esa_safety_margin_ft=1000)
    layer = _layer_with_min_alt()
    selection = MapSelection(base=layer, overlays=[])
    route = Route.from_config(
        "R",
        [
            Waypoint(name="a", position=Position.new((50, 5, 0), (10, 5, 0))),
            Waypoint(name="b", position=Position.new((50, 20, 0), (11, 20, 0))),
        ],
        conf,
    )
    warnings = compute_esa(route, selection, conf)
    # Highest obstacle along the leg is 3200ft; +1000 margin, rounded up to 100.
    assert route.waypoints[1].minimum_leg_alt == 4200
    assert warnings == []


def test_missing_min_alt_warns():
    conf = Config(min_cruise_speed=300, default_cruise_speed=420, dash_speed=540,
                  units=DistanceUnit.NAUTICAL)
    layer = MapLayer(
        name="GERMANY",
        pixel_map={Position.new((50, 0, 0), (10, 0, 0)): PixelMapPoint(
            position=Position.new((50, 0, 0), (10, 0, 0)), x_pixel=0, y_pixel=0)},
        image_file="GERMANY.jpg",
    )
    selection = MapSelection(base=layer, overlays=[])
    route = Route.from_config(
        "R",
        [
            Waypoint(name="a", position=Position.new((50, 5, 0), (10, 5, 0))),
            Waypoint(name="b", position=Position.new((50, 20, 0), (11, 20, 0))),
        ],
        conf,
    )
    warnings = compute_esa(route, selection, conf)
    assert any("no min-altitude" in w for w in warnings)
    assert route.waypoints[1].minimum_leg_alt is None
