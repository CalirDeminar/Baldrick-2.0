# Map Definition Format

Every DCS map is described by a YAML file in the `map_data/` folder, with its
image in `map_data/image_files/`. Maps are discovered automatically on startup.

There are two kinds of map layer:

- **Base maps** whose `name` matches a supported DCS map (`CAUCASUS`, `GERMANY`,
  `NORMANDY`, `NTTR`, `PERSIAN_GULF`, `SYRIA`). A route is placed on the base map
  that fully contains all of its waypoints.
- **HD overlay areas** whose `name` is anything else. These are higher-resolution
  images covering a smaller region. They are auto-associated to the base map whose
  bounds fully contain the overlay's bounds, and are composited on top of the base
  map wherever they overlap a kneeboard.

## Fields

- `name` (required): the map/area name. A value matching a DCS map marks a base map.
- `image_file` (optional): image filename inside `map_data/image_files/`. Defaults
  to `<NAME>.jpg` (uppercased).
- `projection_adjustment_deg` (optional, default `0`): map projection rotation.
- `mag_var` (optional, default `0`): magnetic variation (degrees) for the area.
  Magnetic course shown on cards is `true_course - mag_var`.
- `layer_priority` (optional, default `0`): overlay stacking order. Higher numbers
  are composited on top. Base maps are effectively the lowest layer.
- `pixel_map` (required): a list of lat/long -> pixel anchor points. Any position
  bounded by four anchor points is located by bilinear interpolation. Each entry:
  - `lat`: DMS as `D, M, S`
  - `long`: DMS as `D, M, S`
  - `x_pixel`, `y_pixel`: pixel coordinates in the image
- `min_altitude_map` (optional): tallest-obstacle altitudes on a 30 arc-minute
  grid, used for ESA. Each entry:
  - `lat`: DMS as `D, M, S` (minutes are bucketed to the nearest 0/30 cell)
  - `long`: DMS as `D, M, S`
  - `altitude_ft`: tallest obstacle/terrain in the cell, in feet

## Example base map (`map_data/germany.yaml`)

```yaml
name: Germany
projection_adjustment_deg: -10
mag_var: 2.0
pixel_map:
  - { lat: "56, 0, 0", long: "06, 0, 0", x_pixel: 12960, y_pixel: 478 }
  # ...
min_altitude_map:
  - { lat: "50, 0, 0", long: "10, 0, 0", altitude_ft: 1200 }
  # ...
```

## Example HD overlay (`map_data/germany_frankfurt_hd.yaml`)

```yaml
name: Frankfurt_HD
image_file: FRANKFURT_HD.jpg
projection_adjustment_deg: -10
layer_priority: 10
pixel_map:
  - { lat: "50, 0, 0", long: "08, 0, 0", x_pixel: 0, y_pixel: 24000 }
  # ...
```
