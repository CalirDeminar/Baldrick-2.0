## Map Image Management
The Baldrick 2 app is a Typer CLI app intended to transform user-defined route files, along with user-defined config files into a set of visual navigation kneeboard images.
The base of these images comes from a series of large image files representing the area covered by a single DCS map.
Each of these image files has a matching pixel map file, that maps a grid of DMS lat/long positions to individual pixel positions in the image.
As long as a waypoint's position is bounded by 4 of these individual pixel map points, the position of any lat/long point can be approximated via linear interpolation.

##
Min Altitude Map
For each DCS map, alongside the pixel map a min-altitude map will also exist. This will represent the tallest obstical for that cell on the map. This will be used to define the ESA (emergency safe altitude) for each leg
## ToT Calculator
Used to calculate the speeds and/or ToTs for legs of a route to hit the required ToTs and speed requirements for legs. Will do it's best to stick to multiple of 60 speeds where it can, but will prioritise sticking to speed requirements and ToTs.
A user might enter a combination of WPs that need to be hit at certain times, certain legs requiring certain speeds, and the ToT over target itself. These all need to be worked to get a final set of speeds and ToTs (+ relative ToT from push in a push WP is defined) for each WP

## Fuel Calculator
Used to calculate the BINGO fuel level for the flight, and to also return (descriptive) errors if the route *cannot* be flown without cutting into the defined reserve, or if the aircraft does not have enough fuel full stop for the route.
Fuel consumption is defined by the route, and the fuel map defined in the config being used.
## Error Handling and Warnings
There are a number of scenarios where the input from the user might not be something we can fully handle, or even handle at all
Some of these scenarios might be
- As mentioned above, not enough fuel. Cutting into the reserve or not having enough fuel, would return an error stating the problem, along with the fuel total required for the route as it is currently defined
- ToT Mismatch - ToTs defined in the route, or in the route and the ToT when running the probgram might be out of order or impossible. If Waypoints have the same ToT, or have unreasonably large times between them, also return an error. We can't actually know if we've got wrong order, as a ToT wrapping over midnight might appear to be going backwards, but is actually perfectly valid
- Impossible ToT Limitations - ToTs and speeds defined in a route might end up constraining the ToT calculator such that a route that sticks to all ToTs and speed requirements is impossible. In these cases an error would be raised, listing the problem waypoints
-  WP Out of Bounds - Some number of waypoints in a route might be positioned such that no DCS map pixel map contains all waypoints in a route. This would be returned as an error to the user, highlighting what waypoints are out of bounds for what maps. If Waypoints are spread across multiple possible DCS maps then all of these should be returned with the waypoints outside of each one.
-  Unmapped Fuel Consumption Regime - A route's required speedor defined altitude might be outside of the bounds of the in use fuel map. This doesn't stop us fully, but would need us to just use the nearest possible approximation in the fuel map. This would however return a warning alongside the output kneeboard cards that a particular set of legs were outside of the fuel map bounds (and list what legs they were, the speed and altitude, and the limits of the fuel map)