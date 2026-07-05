Route files are the primary intended way for users to define routes.
They are defined in yaml, and consist of:
A top level name field (value must be a string)
A waypoint list, that must consist of elements of:
* Name: The name for the WP. Required.
* Lat/Long: The Lat/long of the waypoint, defined in DMS (integer). Required. Eventually ideally able to accept Degree Decimal Minutes or MGRS as well
* Tags: An list of tags to apply meaning to the WP. Optional. A flight can have 0 or more tags. These tags can be any of:
  * HOME - the airfield the flight expects to return to
  * DIVERT - a contingency airfield the flight might have to land at instead of their home airfield
  * FIX - an point the flight expects to perform a visual navigation fix at
  * PUSH - the zero point from which relative time on target calculations start from. Also the point after which absolute and relative timing marks and WP tot figures are shown. 
  * IP - a visual identification point the flight expects to see to set them up for an attack on a target. Always depicted on the charts as a square with the bottom face perpendicular to the flight path.
  * TGT - the target the flight is attacking. Will almost always be immediately following an IP tagged WP. Always depicted on the charts as a triangle with the bottom face perpendicular to the flight path
* Notes: These are notes that will be shown on the cards for the flight to reference. These can be things like attack parameters, notes on expected visual references at a point, or anything else the planner thinks the flight might want immediately to hand. Optional.
* Timestamp: A particular timestmap the flight expected to pass the waypoint. This will be an anchor for the ToT and leg-speed calculation system to perform calculations around. Optional. If omitted the, will be calculated by the ToT calculation system. 
* Speed: The speed the planning wants the leg to this WP flown at. This will be an anchor for the ToT and leg-speed calculation system to perform calculations around. Optional. If omitted will be calculated by the ToT calculation system.
* Altitude: The altitude the planner wants the leg to be flown at. This will be shown on the card as reference to the pilot, but also used for the fuel calculations. Optional. If omitted the fuel calculation will assume sea level.