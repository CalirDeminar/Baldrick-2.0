Route files are the primary intended way for users to define routes.
They are defined in yaml, and consist of:
A top level name field (value must be a string)
A waypoint list, that must consist of elements of:
* Name: The name for the WP. Required.
* Lat/Long: The Lat/long of the waypoint. Required unless `mgrs` is supplied. Each coordinate accepts:
  * DMS (degrees, minutes, seconds) as `"D, M, S"` or `"D M S"` (commas or spaces)
  * DDM (degree decimal minutes) as `"D MM.M"` with optional hemisphere prefix/suffix (`N`, `S`, `E`, `W`)
* Mgrs: An optional MGRS grid reference (e.g. `"32U MV 12345 67890"`) that replaces lat/long for the waypoint. MGRS may also be supplied in the `lat` field alone.
* Tags: An list of tags to apply meaning to the WP. Optional. A flight can have 0 or more tags. These tags can be any of:
  * HOME - the airfield the flight expects to return to
  * DIVERT - a contingency airfield the flight might have to land at instead of their home airfield. Not part of the flown route sequence: excluded from ToT, ESA, and minimum fuel calculations, and no route line is drawn to it. Used for bingo fuel when nearer than HOME from the furthest point of the route. Rendered at the end of the kneeboard output as contingency cards and notes.
  * FIX - an point the flight expects to perform a visual navigation fix at
  * PUSH - the zero point from which relative time on target calculations start from. Also the point after which absolute and relative timing marks and WP tot figures are shown. 
  * IP - a visual identification point the flight expects to see to set them up for an attack on a target. Always depicted on the charts as a square with the bottom face perpendicular to the flight path.
  * TGT - the target the flight is attacking. Will almost always be immediately following an IP tagged WP. Always depicted on the charts as a triangle with the bottom face perpendicular to the flight path
  * AAR - a waypoint marking the rough tanker track area where the flight can take on fuel. The fuel calculator treats it as a refuel point: waypoints before an AAR only need enough fuel to reach it (arriving with reserve intact), and the minimum fuel required leaving the tanker to complete the remainder of the route is reported separately.
* Notes: These are notes that will be shown on the cards for the flight to reference. These can be things like attack parameters, notes on expected visual references at a point, or anything else the planner thinks the flight might want immediately to hand. Optional.
* Timestamp: A particular timestmap the flight expected to pass the waypoint. This will be an anchor for the ToT and leg-speed calculation system to perform calculations around. Optional. If omitted the, will be calculated by the ToT calculation system. 
* Speed: The speed the planning wants the leg to this WP flown at. This will be an anchor for the ToT and leg-speed calculation system to perform calculations around. Optional. If omitted will be calculated by the ToT calculation system.
* Altitude: The altitude the planner wants the leg to be flown at. This will be shown on the card as reference to the pilot, but also used for the fuel calculations. Optional. If omitted the fuel calculation will assume sea level.

An optional top-level `flot` list defines the Forward Line of Own Troops (FLOT). Each entry is a point with the same coordinate formats as waypoints (`lat`/`long`, DDM, or `mgrs`). Points are connected in order by dashed red line segments on the overview and per-leg kneeboard cards. Any route leg that crosses the FLOT receives a red `! FLOT CROSSED THIS LEG` warning in the doghouse. At least two points are required for the FLOT to be drawn.
