Fuel maps are ways for users to describe to the system how their aircraft consumes fuel. 
It represents an aircraft in a given loading configuration, and consists of a name, a fuel capacity and a fuel consumption map.


The format of this map consists of:
* Name: a name for the fuel map, and how the user will reference it.
* Capacity: The amount of fuel the aircraft can carry in this configuration.
* Capacity_unit (optional, default `lb`): unit for capacity. One of `lb`, `kg`, `gal`, `l`.
* Consumption_volume_unit (optional, default `lb`): default volume unit for row `consumption` values.
* Consumption_distance_unit (optional, default `nm`): default distance basis for row `consumption` values.
* Consumption_time_unit (optional): default time basis for row `consumption` values (`min` or `hr`). Mutually exclusive with distance units.
* FuelMap: A list of consumption figures to make up a fuel consumption matrix:
    * altitude_ft - This consumption figure is defined for this altitude
    * speed_kts - This consumption figure is defined for this speed
    * lb_per_nm - lb of fuel used per nautical mile traveled (legacy format, still supported).
    * consumption - fuel consumption amount when not using `lb_per_nm`.
    * consumption_volume_unit (optional per row) - volume unit for `consumption`.
    * consumption_distance_unit (optional per row) - `nm` or `km`.
    * consumption_time_unit (optional per row) - `min` or `hr`. Time-based consumption is converted to lb/nm using the row's `speed_kts`.

Volume units (`gal`, `l`) are converted to pounds using Jet-A density assumptions (6.7 lb/US gal, 1.77 lb/L).

The fuel calculation system will take the matrix that the user defines, and if altitudes or speeds not in the matrix are used, will use linear interpolation to make a best best guess at an actual consumption figure.

All values are normalised internally to pounds and lb/nm regardless of the units used in the file.
