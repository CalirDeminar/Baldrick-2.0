from typing import TYPE_CHECKING
from enums import Tag


if TYPE_CHECKING:
    from route.route import Route
    from config.config import Config

# Fuel Counts
# - Planned Fuel - Min Fuel to complete mission with expected route and reserve
# - BINGO
# - JOKER

def calculate_max_return_distance(route: 'Route', conf: 'Config', is_bingo: bool = False) -> tuple[Tag, float]:
    home_wp = None
    divert_wp = None
    for wp in route.waypoints:
        if Tag.HOME in wp.tags:
            home_wp = wp
        if Tag.DIVERT in wp.tags:
            divert_wp = wp
    if not home_wp:
        raise Exception("No home wp found")
    max_distance: float = 0.0
    furthest_wp = None
    for wp in route.waypoints:
        if wp is not home_wp and wp is not divert_wp:
            wp_home_distance = wp.position.distance_from(home_wp.position, conf.units)
            if not furthest_wp or wp_home_distance > max_distance:
                max_distance = wp_home_distance
                furthest_wp = wp
    return_type = Tag.HOME
    if is_bingo and furthest_wp and divert_wp and furthest_wp.position.distance_from(divert_wp.position, conf.units) < max_distance:
        max_distance = furthest_wp.position.distance_from(divert_wp.position, conf.units)
        return_type = Tag.DIVERT
    return return_type, max_distance
