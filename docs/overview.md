# Baldrick 2 Overview
## Introduction
Baldrick 2 is a CLI application that creates map and route kneeboards for low level navigation in flight simulators, with the primary intended one being DCS World.
It is a rewrite and update to the existing Baldrick application of roughly the same goal. That codebase can be found at: https://github.com/CalirDeminar/Baldrick
## Functional Requirements
With the config file set to the users liking, the user can define a route in a YAML file, documented in the route_file_format.md file, or via an interactive route builder. 

Given the route via either method, the user then defines if they want to use a config override, define a time on target or a push time.

Using the above, the fuel map referenced in the config, their defined targets, Baldrick 2 then calculates the following
* Leg speeds and ToTs (time on target) for each waypoint in the route (sticking to multiple of 60 speeds where possible to aid pilot timekeeping)
* A bingo fuel for the route (Minimum fuel needed to get back to either the home airfield or divert airfield from the furthest point of the route)

It then uses the above, plus internal maps and pixel to lat/long mappings against those maps, to create a series of kneeboards of a fixed 1600x2400 pixels that consist of:
* A cropped and rotated section of the map that shows the leg of the route (with some padding around the edge of the leg so the surroundings are able to be seen)
* An overlay of the route. The leg of the current kneeboard being marked as a line in the route colour, and other legs not for the current kneeboard, the same colour but with a level of transparency
* Waypoints marked as a circle of the route colour (With the line connecting to the edge of the circle, but not being drawn within the hollow inside of the circle).IP waypoints are instead marked with a square, and target waypoints being marked with a triangle
* Information laid out in a block in one corner, containing:
  * The name of the leg (WP: X)
  * The magnetic course to be flown for the leg (MC: X°)
  * The length of the leg in units matching the config (nm, km, miles) (Dist: X.Ynm)
  * The ToT to arrive at the end of the leg (ETA: HH:MM:SS). Ideally with an absolute time *and* a relative time to a push point, if a push point is included (to be able to handle a delay/rolex to the expected push time)
  * The emergency safe altitude for the leg. This is an the altitude of the highest feature around the leg, plus a saftey margin, that the crew must climb to if they suddenly enter IMC and are at immediate risk of collision with the ground of obsticals.
  * Speed for the leg to be flown (TAS: Xkts)
  * The magnetic course to be flown for the *next* heading (NMC: X°)
  * For FIX points, the lat/long of the fix point
  * Any notes defined for the leg
## Other md references
Architecture Notes 
Config Format
Fuel Map Format
Route File Format
## Technical Requirements
- Use the typer CLI library to define the CLI app itself
- Use the questionary library for any quesiton/answer input such as the interactive route builder
- Minimise memory usage while processing image files
- Try to keep execution time down. So multithread around potentially expensive operations if that might significantly improve execution time (without sacrificing memory consumption significantly)