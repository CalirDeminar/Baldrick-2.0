Fuel maps are ways for users to describe to the system how their aircraft consumes fuel. 
It represents an aircraft in a given loading configuration, and consists of a name, a fuel capacity and a fuel consumption map.


The format of this map consists of:
* Name: a name for the fuel map, and how the user will reference it.
* Capacity: The amount of the the aircraft can carry in this configuration, in lbs.
* FuelMap: A list of consumption figures to make up a fuel consumption matrix:
    * altitude_ft - This consumption figure is defined for this altitude
    * speed_kts - This consumption figure is defined for this speed
    * lb_per_nm - lb of fuel used per nautical mile traveled.

The fuel calculation system will take the matrix that the user defines, and if altitudes or speeds not in the matrix are used, will use linear interpolation to make a best best guess at an actual consumption figure.

Future work would be to make this format more open, allowing for fuel volume (for the figure per mile, or capacity values) definable in lbs, kg, gallons or liters. With the consumption figure definable in those units per nautical mile or per kilometer, OR in those units per minute or per hour.