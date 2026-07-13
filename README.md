# Baldrick 2

Baldrick 2 is a CLI tool that plans low-level navigation routes and generates map kneeboards for flight simulators, primarily [DCS World](https://www.digitalcombatsimulator.com/). Given a route and config (and optionally a fuel map), it calculates leg speeds and times, emergency safe altitudes, and renders a set of 1600×2400 JPEG kneeboard cards. When a fuel map is configured it also calculates bingo fuel and related figures.

## Installation

Download and extract the Baldrick release bundle. You should have a folder similar to:

```
baldrick/
  baldrick.exe
  config.yaml
  routes/
  fuel_maps/
  _internal/          # bundled map data and runtime (do not edit)
```

Run `baldrick.exe` from that folder (or add the folder to your `PATH`). Map images and pixel maps live inside `_internal/`; you do not need to install Python or any other dependencies.

## Quick start

1. Edit `config.yaml` beside `baldrick.exe` to point at a fuel map and set your preferred speeds/units.
2. Place route YAML files in the `routes/` folder (see `routes/example_route_file.yaml`).
3. Open a terminal in the Baldrick folder and run:

```cmd
baldrick.exe --route example_route_file
```

Kneeboards are written to `output/<route name>/`.

## Running the app

```cmd
baldrick.exe [OPTIONS]
```

| Option | Short | Description |
|--------|-------|-------------|
| `--route` | `-r` | Route file name **without** `.yaml`, looked up in `routes/` |
| `--config` | `-c` | Named override from `config.yaml` (e.g. `warbirds`, `metric`) |
| `--tot` | `-t` | Time on target at the **TGT** waypoint, `HH:MM:SS` |
| `--push` | `-p` | Push time at the **PUSH** waypoint, `HH:MM:SS` |

If `--route` is omitted, Baldrick launches an interactive route builder (prompts in the terminal).
if `--config` is omitted, Baldrick will use the default top level config parameters

### Examples

```cmd
REM Plan from a route file with default config
baldrick.exe -r example_route_file

REM Use the "warbirds" config override
baldrick.exe -r example_route_file -c warbirds

REM Set time on target at the TGT waypoint
baldrick.exe -r example_route_file -t 12:35:00

REM Set push time and time on target together
baldrick.exe -r my_route -p 12:00:00 -t 12:35:00

REM Build a route interactively
baldrick.exe
```

On success the CLI prints bingo fuel and total fuel required when a fuel map is configured, any warnings, and the output folder path. On failure it prints `Error: …` and exits with code 1.

## Folder layout

User-editable files sit next to `baldrick.exe`:

| Path | Purpose |
|------|---------|
| `config.yaml` | Global preferences, fuel map selection, named overrides |
| `routes/` | Route YAML files |
| `fuel_maps/` | Aircraft fuel consumption maps |
| `output/` | Generated kneeboards (created on run) |

Map data is bundled inside `_internal/` and is not user-editable.

Supported base DCS maps: `CAUCASUS`, `GERMANY`, `NORMANDY`, `NTTR`, `PERSIAN_GULF`, `SYRIA`. All waypoints in a route must fall within one base map. When a route fits more than one map (for example, Germany and Normandy), Baldrick prompts you to choose unless the route file sets an optional `map:` field. Higher-resolution HD overlay areas are composited automatically where they overlap a kneeboard.

## Config file (`config.yaml`)

The config defines display and planning defaults. Only one config is active; named **overrides** let you swap settings (e.g. warbird speeds) without maintaining separate config files.

### Top-level fields

| Field | Description |
|-------|-------------|
| `route_colour` | Hex colour for route lines on kneeboards (e.g. `"#000000"`) |
| `min_cruise_speed` | Lowest speed the ToT planner may assign to a cruise leg |
| `default_cruise_speed` | Speed used when no ToT or leg speed is specified |
| `dash_speed` | Speed flown on the IP → TGT leg |
| `units` | `NAUTICAL` (kts / nm / ft), `METRIC` (km/h / km / m), or `IMPERIAL` (mph / mi / ft) |
| `fuel_map` | Optional. Name of the fuel map file in `fuel_maps/` (without `.yaml`). Omit, set to `null`, or leave blank to skip fuel calculations |
| `reserve_fuel` | Minimum fuel the aircraft should still have on reaching HOME or DIVERT (lb) |
| `takeoff_fuel` | Fuel consumed before the route planning begins (startup, taxi, takeoff; lb) |
| `rtb_altitude` | Altitude assumed for return-to-base bingo/joker calculations |
| `rtb_speed` | Speed assumed for return-to-base bingo/joker calculations |
| `esa_safety_margin_ft` | Feet added above the tallest obstacle when computing ESA (default `1000`) |
| `overview_card_downsample_factor` | Downscale factor for the route overview card (default `3`) |
| `card_alpha` | Optional. Output-card opacity `0`–`255` (`255` = fully opaque). Omit or `null` for opaque JPEG output; lower values save cards as PNG with transparency (for DCS 2D kneeboard overlays) |
| `overrides` | Optional list of named override blocks (see below) |

### Overrides

Each override has a `name` and any subset of the overridable fields above (`route_colour`, speeds, `units`, `fuel_map`, `takeoff_fuel`, `reserve_fuel`, `rtb_altitude`, `rtb_speed`, `overview_card_downsample_factor`, `esa_safety_margin_ft`, `card_alpha`). Pass the name with `--config` / `-c`.

Example:

```yaml
overrides:
  - name: warbirds
    min_cruise_speed: 220
    default_cruise_speed: 220
    dash_speed: 220
    units: IMPERIAL
  - name: metric
    units: METRIC
    min_cruise_speed: 660
    default_cruise_speed: 780
    dash_speed: 1000
```

## Route files (`routes/*.yaml`)

Route files define the flight path and optional timing/speed constraints.

### Structure

```yaml
name: My Route
# map: GERMANY   # optional: force base map when route fits multiple maps
waypoints:
  - name: Ramstein
    lat: 49, 26, 30
    long: 07, 37, 30
    tags: [HOME]
  - name: IP
    lat: "51 8.5"
    long: "10 14.5"
    tags: [IP]
  - name: TGT
    lat: 50, 59, 30
    long: 10, 16, 30
    tags: [TGT]
    timestamp: "12:35:00"
    speed: 540
    altitude: 500
    notes: "Railyard"
```

### Route fields

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Route name (output folder and card titles) |
| `map` | No | Base DCS map name (e.g. `GERMANY`, `NORMANDY`). Use when a route fits multiple maps and you want to skip the interactive prompt |
| `flot` | No | Forward line of troops as a list of lat/long points |
| `waypoints` | Yes | Ordered list of waypoints (see below) |

### Waypoint fields

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Waypoint name (shown on cards) |
| `lat` / `long` | Yes* | Coordinates (see formats below) |
| `mgrs` | No | MGRS grid reference; replaces `lat`/`long` when present |
| `tags` | No | List of waypoint tags (see below) |
| `notes` | No | Free text shown on the leg card (`\n` for line breaks) |
| `timestamp` | No | Fixed time at this waypoint, `HH:MM:SS` (ToT anchor) |
| `speed` | No | Required leg speed **to** this waypoint (kts / mph / km/h per config units) |
| `altitude` | No | Leg altitude for display and fuel calc (defaults to sea level) |

\*Not required when `mgrs` is supplied.

### Coordinate formats

**DMS** (degrees, minutes, seconds) — commas or spaces:

```yaml
lat: 49, 26, 30
long: 07, 37, 30
# or
lat: "49 26 30"
```

**DDM** (degree decimal minutes) — optional hemisphere prefix/suffix:

```yaml
lat: "N51 30.5"
long: "10 30.0 E"
```

**MGRS** — full grid reference in `mgrs`, or in `lat` alone:

```yaml
mgrs: "32U MV 12345 67890"
# or
lat: "32U MV 12345 67890"
```

### Waypoint tags

| Tag | Meaning |
|-----|---------|
| `HOME` | Return airfield; required for bingo/joker fuel |
| `DIVERT` | Contingency airfield; used for bingo if nearer than HOME from the furthest point |
| `FIX` | Visual fix; lat/long shown on the card |
| `PUSH` | Push time zero point; relative ETAs shown after this waypoint |
| `IP` | Initial point; drawn as a square on the map |
| `TGT` | Target; drawn as a triangle; `--tot` applies here |

The IP → TGT leg always uses `dash_speed` from config unless the TGT waypoint specifies its own `speed`.

## Fuel maps (`fuel_maps/*.yaml`)

Fuel maps describe how much fuel an aircraft burns at various speeds and altitudes. Values are normalised internally to **pounds** and **lb/nm** regardless of the units used in the file.

### Structure

```yaml
name: F4-6-2
capacity: 16,800
capacity_unit: lb          # optional: lb, kg, gal, l
fuelMap:
  - altitude_ft: 0
    speed_kts: 420
    lb_per_nm: 29.71
  - altitude_ft: 4000
    speed_kts: 420
    consumption: 1200
    consumption_volume_unit: lb
    consumption_time_unit: hr
```

Reference the map from config with `fuel_map: F4-6-2` (filename without `.yaml`). To skip fuel planning entirely, omit `fuel_map` or set it to `null`.

### Top-level fields

| Field | Description |
|-------|-------------|
| `name` | Identifier (must match how you reference it; min 3 characters) |
| `capacity` | Total usable fuel in this loading configuration |
| `capacity_unit` | Optional. `lb` (default), `kg`, `gal`, or `l` |
| `consumption_volume_unit` | Optional default volume unit for row `consumption` values |
| `consumption_distance_unit` | Optional default distance basis: `nm` or `km` |
| `consumption_time_unit` | Optional default time basis: `min` or `hr` (mutually exclusive with distance) |
| `fuelMap` | List of consumption matrix rows |

### Row fields

Each row in `fuelMap` defines one point in the speed/altitude matrix:

| Field | Description |
|-------|-------------|
| `altitude_ft` | Altitude in feet |
| `speed_kts` | Speed in knots |
| `lb_per_nm` | Legacy format: pounds per nautical mile |
| `consumption` | Alternative to `lb_per_nm`; amount in the configured volume unit |
| `consumption_volume_unit` | Per-row volume unit override |
| `consumption_distance_unit` | Per-row distance unit override (`nm` or `km`) |
| `consumption_time_unit` | Per-row time unit override (`min` or `hr`); converted to lb/nm using `speed_kts` |

Volume units (`gal`, `l`) are converted using Jet-A density (6.7 lb/US gal, 1.77 lb/L).

If a leg's speed or altitude falls outside the matrix, Baldrick clamps to the nearest edge and emits a **warning** (planning continues).

## Output

Each run creates `output/<route name>/` containing:

| File | Description |
|------|-------------|
| `<MAP>-02-wp01.jpg` … `<MAP>-02-wpNN.jpg` | One kneeboard per route leg (1600×2400 JPEG, or `.png` when `card_alpha` is below 255) |
| `<MAP>-01-Overview.jpg` | Whole-route overview with fuel summary (`.png` when semi-transparent) |
| `<MAP>-00-Legend.jpg` | Symbol and doghouse field key (`.png` when semi-transparent) |
| `notes.txt` | Text summary: ETAs, speeds, ESA, min fuel to complete route, bingo/joker |
| `<route name>.zip` | Zip archive of the folder contents |

Each leg card includes a cropped, rotated map section, route overlay (current leg solid, others faded), waypoint markers, and a doghouse block with WP name, magnetic course, distance, ETA (absolute and relative to push when applicable), ESA, TAS, next magnetic course, fix coordinates, and notes.

## Errors

Baldrick stops immediately and prints `Error: …` for the following. All inherit from `BaldrickError`.

### Route not found

```
Route file not found: …/routes/my_route.yaml
```

The `--route` name does not match a file in `routes/`.

### Map errors (`MapError`)

Raised when no supported DCS base map fully contains every waypoint. The message lists each base map and which waypoints fall outside its bounds:

```
No supported map fully contains this route.
  GERMANY: waypoints out of bounds: OCEAN
  CAUCASUS: waypoints out of bounds: Ramstein, IP, TGT
```

### Time-on-target errors (`ToTError`)

Raised when fixed timestamps and speed constraints cannot be satisfied:

| Situation | Example message |
|-----------|-----------------|
| Two waypoints share the same time | `Waypoints 'A' and 'B' have the same time-on-target.` |
| Unreasonably long gap between anchors | `The time between waypoints 'A' and 'B' is unreasonably large (15.0 h); check their timestamps.` |
| Fixed-speed legs exceed available time | `Segment 'A' -> 'B' is impossible: the fixed-speed legs alone take longer than the 0.50 h allowed between their times.` |
| No time left for cruise legs | `Segment 'A' -> 'B' is impossible: there is no time left for its cruise legs after the fixed-speed legs.` |

Midnight wraps (a later waypoint with an earlier clock time) are handled automatically by adding 24 hours.

### Fuel / config errors

| Situation | Example message |
|-----------|-----------------|
| Named fuel map file missing | `Fuel map 'F4-6-2' not found at … Omit or null 'fuel_map' in config.yaml to skip fuel calculations.` |
| Route exceeds capacity | `Route requires 18500 lb of fuel … but the 'F4-6-2' capacity is only 16800 lb (short by 1700 lb). The route cannot be flown without cutting into the reserve.` |

### Input validation errors

Invalid YAML structure, coordinates, timestamps, or fuel map units may raise `ValueError` or Pydantic validation errors during file loading. These appear as Python tracebacks rather than the formatted `Error:` line. Common causes:

- Waypoint missing both `lat`/`long` and `mgrs`
- Invalid coordinate string or MGRS reference
- Invalid `HH:MM:SS` timestamp
- Unknown fuel unit name
- Config override name not found in `overrides`

## Warnings

Warnings do **not** stop the run. They are printed in yellow and also included in `notes.txt`.

| Source | When |
|--------|------|
| ToT planner | No timed waypoints supplied; default cruise speed used |
| ToT planner | `--tot` given but route has no TGT waypoint |
| ToT planner | `--push` given but route has no PUSH waypoint |
| ToT planner | Segment could not keep a multiple-of-60 cruise speed |
| Fuel calculator | No fuel map configured (fuel planning skipped) |
| Fuel calculator | Leg speed/altitude outside fuel map bounds |
| Fuel calculator | RTB profile outside fuel map bounds |
| Fuel calculator | Route has no HOME waypoint (bingo/joker skipped) |
| ESA calculator | Map has no min-altitude data |
| ESA calculator | One or more legs lack min-altitude coverage |

## Further reading

Detailed design notes live in `docs/`:

- [`docs/overview.md`](docs/overview.md) — functional overview
- [`docs/route_file_format.md`](docs/route_file_format.md) — route file reference
- [`docs/fuel_map_format.md`](docs/fuel_map_format.md) — fuel map reference
- [`docs/config_format`](docs/config_format) — config reference
- [`docs/map_definition_format.md`](docs/map_definition_format.md) — bundled map data format
- [`docs/architecture_notes.md`](docs/architecture_notes.md) — algorithms and error-handling design

## Building from source

For development or creating your own release bundle:

- Python 3.13+
- [uv](https://docs.astral.sh/uv/)

```bash
git clone <repo-url>
cd Baldrick_2
uv sync
uv run python build.py
```

The distributable is written to `dist/baldrick/` with `baldrick.exe`, `config.yaml`, `routes/`, and `fuel_maps/` beside the executable. Map data ships inside `_internal/`.
