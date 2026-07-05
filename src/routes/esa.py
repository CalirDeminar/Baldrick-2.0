"""Emergency safe altitude (ESA) calculation.

The ESA for a leg is the tallest obstacle within the leg's cells plus a safety
margin, rounded up so the crew has a single clean altitude to climb to on
entering IMC. Requires a min-altitude map for the selected base map; when none
is available every leg's ESA is left unset and a warning is emitted.
"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING

from units import altitude_from_ft

if TYPE_CHECKING:
    from config.config import Config
    from routes.map import MapSelection
    from routes.route import Route


def _round_up_100(value: float) -> int:
    return int(math.ceil(value / 100.0) * 100)


def compute_esa(route: "Route", selection: "MapSelection", conf: "Config") -> list[str]:
    """Populate ``waypoint.minimum_leg_alt`` (in the route's altitude units) for
    each leg. Returns warnings."""
    min_alt = selection.base.min_alt
    if min_alt is None:
        return [
            f"Map '{selection.base.name}' has no min-altitude data; "
            f"ESA will be shown as N/A."
        ]

    warnings: list[str] = []
    missing = 0
    for i in range(1, len(route.waypoints)):
        a = route.waypoints[i - 1]
        b = route.waypoints[i]
        highest_ft = min_alt.min_alt_between(a.position, b.position)
        if highest_ft is None:
            missing += 1
            continue
        esa_ft = _round_up_100(highest_ft + conf.esa_safety_margin_ft)
        b.minimum_leg_alt = int(round(altitude_from_ft(esa_ft, route.units)))

    if missing:
        warnings.append(
            f"{missing} leg(s) had no min-altitude coverage; their ESA is shown as N/A."
        )
    return warnings
