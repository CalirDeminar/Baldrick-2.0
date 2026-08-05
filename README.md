# Baldrick 2

Baldrick 2 is a CLI tool that plans low-level navigation routes and generates map kneeboards for flight simulators, primarily [DCS World](https://www.digitalcombatsimulator.com/). Given a route and config (and optionally a fuel map), it calculates leg speeds and times, emergency safe altitudes, and bingo fuel, then renders a set of 1600×2400 kneeboard cards.

## Installation

Download the latest release from GitHub and extract the bundle. You should have a folder similar to:

```
baldrick/
  baldrick.exe
  config.yaml
  routes/
  fuel_maps/
  _internal/          # bundled map data and runtime (do not edit)
```

No Python or other dependencies are required. Run `baldrick.exe` from that folder (or add the folder to your `PATH`).

1. Edit `config.yaml` to set speeds, units, and (optionally) a fuel map.
2. Place route YAML files in `routes/` (see `routes/example_route_file.yaml`).
3. From a terminal in the Baldrick folder:

```cmd
baldrick.exe --route example_route_file
```

Kneeboards are written to `output/<route name>/`.

### Folder layout

| Path | Purpose |
|------|---------|
| `config.yaml` | Global preferences, fuel map selection, named overrides |
| `routes/` | Route YAML files |
| `fuel_maps/` | Aircraft fuel consumption maps |
| `output/` | Generated kneeboards (created on run) |
| `_internal/` | Bundled map data and runtime (not user-editable) |

Supported base DCS maps: `CAUCASUS`, `GERMANY`, `NORMANDY`, `NTTR`, `PERSIAN_GULF`, `SYRIA`. All waypoints in a route must fall within one base map. When a route fits more than one map, Baldrick prompts you to choose unless the route sets an optional `map:` field. Higher-resolution HD overlay areas are composited automatically where they overlap a kneeboard.

---

## File setup

### Config (`config.yaml`)

There is one active config. Named **overrides** let you swap settings for different aircraft or unit systems without maintaining separate config files.

#### Top-level fields

These three speed fields are **required**:

| Field | Description |
|-------|-------------|
| `min_cruise_speed` | Lowest speed the ToT planner may assign to a cruise leg |
| `default_cruise_speed` | Speed used when no ToT or leg speed is specified |
| `dash_speed` | Speed flown on the IP → TGT leg (unless the TGT waypoint sets its own `speed`) |

Optional fields (with defaults):

| Field | Default | Description |
|-------|---------|-------------|
| `route_colour` | `"#000000"` | Hex colour for route lines on kneeboards |
| `units` | `NAUTICAL` | `NAUTICAL` (kts / nm / ft), `METRIC` (km/h / km / m), or `IMPERIAL` (mph / mi / ft) |
| `fuel_map` | none | Filename stem in `fuel_maps/` **without** `.yaml` (e.g. `example_fuel_map`). Omit, `null`, or blank to skip fuel calculations |
| `reserve_fuel` | `0` | Minimum fuel (lb) the aircraft should still have on reaching HOME or DIVERT |
| `takeoff_fuel` | `0` | Fuel (lb) consumed before route planning begins (startup, taxi, takeoff) |
| `rtb_altitude` | `14000` | Altitude for return-to-base bingo/joker calculations (in config altitude units) |
| `rtb_speed` | `420` | Speed for return-to-base bingo/joker calculations (in config speed units) |
| `esa_safety_margin_ft` | `1000` | Feet added above the tallest obstacle when computing ESA |
| `overview_card_downsample_factor` | `3` | Downscale factor for the route overview card |
| `card_alpha` | opaque | Output-card opacity `0`–`255`. Omit or `null` for opaque JPEG; lower values save PNG with transparency (for DCS 2D kneeboard overlays) |
| `turn_g` | `2.0` | Coordinated turn load factor for turn-radius geometry (must be &gt; 1; ~2G ≈ 60° bank) |
| `turn_rate_deg_per_sec` | none | Optional maximum turn rate in deg/s (e.g. radar limits). Omit or `null` for no rate limit |
| `overrides` | `[]` | Named override blocks (see below) |

`fuel_map` references the **filename** of the map file, not the `name` field inside that YAML. For example `fuel_map: example_fuel_map` loads `fuel_maps/example_fuel_map.yaml`, whose internal `name` may be `F4-6-2`.

#### Overrides

Each override has a `name` and any subset of the overridable fields above. Pass the name with `--config` / `-c`. Only fields you list are changed; everything else keeps the base value.

**Nullable clears:** only `fuel_map` and `card_alpha` can be explicitly cleared with `null` (or blank) in an override. Setting other fields to `null` leaves the base value unchanged.

**Typical use cases:**

- **Different aircraft** — swap `fuel_map`, `takeoff_fuel`, `reserve_fuel`, and speeds for that module’s loading.
- **Warbirds / props** — lower speeds and switch to `IMPERIAL`.
- **Metric display** — switch `units` to `METRIC` and use km/h-scale speeds.
- **No fuel planning** — set `fuel_map: null` for a named override that skips bingo/joker.

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
  - name: a4e
    fuel_map: A4E_6-0
    takeoff_fuel: 800
    reserve_fuel: 500
    min_cruise_speed: 300
    default_cruise_speed: 360
    dash_speed: 420
  - name: no_fuel
    fuel_map: null
```

```cmd
baldrick.exe -r my_route -c a4e
```

---

### Fuel maps (`fuel_maps/*.yaml`)

Fuel maps describe how an aircraft burns fuel at various speeds and altitudes for a given loading. Values are normalised internally to **pounds** and **lb/nm**; kneeboard and console fuel figures are always reported in **lb**.

Reference a map from config with `fuel_map: <filename_without_.yaml>`. To skip fuel planning, omit `fuel_map` or set it to `null`.

#### Structure

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

See `fuel_maps/example_fuel_map.yaml` for a full matrix.

#### Top-level fields

| Field | Description |
|-------|-------------|
| `name` | Identifier shown in warnings/errors (min 3 characters). Does **not** need to match the filename |
| `capacity` | Total usable fuel in this loading (commas allowed, e.g. `16,800`) |
| `capacity_unit` | Optional. `lb` (default), `kg`, `gal`, or `l` |
| `consumption_volume_unit` | Optional default volume unit for row `consumption` values |
| `consumption_distance_unit` | Optional default distance basis: `nm` or `km` |
| `consumption_time_unit` | Optional default time basis: `min` or `hr` (mutually exclusive with distance) |
| `fuelMap` | List of consumption matrix rows (camelCase key) |

#### Row fields

Each row defines one point in the speed/altitude matrix. Matrix axes are always **feet** and **knots**, regardless of config units.

| Field | Description |
|-------|-------------|
| `altitude_ft` | Altitude in feet |
| `speed_kts` | Speed in knots |
| `lb_per_nm` | Legacy format: pounds per nautical mile |
| `consumption` | Alternative to `lb_per_nm`; amount in the configured volume unit |
| `consumption_volume_unit` | Per-row volume unit override (`lb`, `kg`, `gal`, `l`) |
| `consumption_distance_unit` | Per-row distance unit override (`nm` or `km`) |
| `consumption_time_unit` | Per-row time unit override (`min` or `hr`); converted to lb/nm using `speed_kts` |

Volume units (`gal`, `l`) are converted using Jet-A density (6.7 lb/US gal, 1.77 lb/L).

Baldrick **interpolates** within the matrix. If a leg’s speed or altitude falls outside the mapped bounds, values are **clamped** to the nearest edge and a warning is emitted (planning continues).

---

### Route files (`routes/*.yaml`)

Route files define the flight path and optional timing/speed constraints. See `routes/example_route_file.yaml`.

#### Structure

```yaml
name: My Route
# map: GERMANY   # optional: force base map when the route fits multiple maps
flot:            # optional Forward Line of Own Troops
  - lat: 51, 10, 8
    long: 10, 13, 49
  - lat: 50, 38, 16
    long: 09, 54, 56
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
    notes: "Railyard\nValley crossways"
  - name: Wiesbaden
    lat: 50, 02, 29
    long: 8, 19, 31
    tags: [DIVERT]
    notes: "TACAN 88X\n07/25"
```

#### Route fields

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Route name (output folder and card titles) |
| `map` | No | Base DCS map name (e.g. `GERMANY`). Use when a route fits multiple maps and you want to skip the interactive prompt |
| `flot` | No | Forward Line of Own Troops as a list of lat/long (or MGRS) points |
| `waypoints` | Yes | Ordered list of waypoints |

#### Waypoint fields

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Waypoint name (shown on cards) |
| `lat` / `long` | Yes* | Coordinates (see formats below). Key is `long`, not `lon` |
| `mgrs` | No | MGRS grid reference; replaces `lat`/`long` when present |
| `tags` | No | List of waypoint tags (see below) |
| `notes` | No | Free text shown on the leg card. Use literal `\n` for line breaks |
| `timestamp` | No | Fixed time at this waypoint, `HH:MM:SS` (ToT anchor) |
| `speed` | No | Required leg speed **to** this waypoint (in config units: kts / mph / km/h) |
| `altitude` | No | Leg altitude for display and fuel calc (in config altitude units; defaults to sea level) |

\*Not required when `mgrs` is supplied (or MGRS is placed in `lat` alone).

#### Coordinate formats

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

#### Waypoint tags

| Tag | Meaning |
|-----|---------|
| `HOME` | Return airfield; required for bingo/joker fuel |
| `DIVERT` | Contingency airfield. **Not part of the flown route**: no route line, excluded from ToT, ESA, and min-fuel calculations. Used for bingo if nearer than HOME from the furthest point of the route. Rendered as separate contingency cards |
| `FIX` | Visual fix; lat/long shown on the card |
| `PUSH` | Push time zero point; relative ETAs shown after this waypoint. CLI `--push` applies here |
| `IP` | Initial point; drawn as a square on the map |
| `TGT` | Target; drawn as a triangle; CLI `--tot` applies here |
| `AAR` | Air-to-air refueling point. Fuel planning treats it as a top-up: legs before AAR only need enough fuel to reach it with reserve intact; minimum fuel to complete the remainder after tanker is reported separately |

Multiple tags per waypoint are allowed (e.g. `tags: [IP, FIX]`). The IP → TGT leg always uses `dash_speed` from config unless the TGT waypoint specifies its own `speed`.

#### FLOT (Forward Line of Own Troops)

Optional top-level `flot` list. Each entry uses the same coordinate formats as waypoints. Points are connected in order by a dashed red line on the overview and per-leg cards. Any route leg that crosses the FLOT receives a red `! FLOT CROSSED THIS LEG` warning in the doghouse. At least **two** points are required for the FLOT to be drawn. FLOT cannot be entered via the interactive builder — YAML only.

---

## Running the app

```cmd
baldrick.exe [OPTIONS]
```

| Option | Short | Description |
|--------|-------|-------------|
| `--route` | `-r` | Route file name **without** `.yaml`, looked up in `routes/` |
| `--config` | `-c` | Named override from `config.yaml` (e.g. `warbirds`, `a4e`) |
| `--tot` | `-t` | Time on target at the **TGT** waypoint, `HH:MM:SS` |
| `--push` | `-p` | Push time at the **PUSH** waypoint, `HH:MM:SS` |

- If `--route` is omitted, Baldrick launches the **interactive route builder**.
- If `--config` is omitted, the top-level config values are used.

### Examples

```cmd
REM Plan from a route file with default config
baldrick.exe -r example_route_file

REM Use a named config override
baldrick.exe -r example_route_file -c warbirds

REM Set time on target at the TGT waypoint
baldrick.exe -r example_route_file -t 12:35:00

REM Set push time and time on target together
baldrick.exe -r my_route -p 12:00:00 -t 12:35:00

REM Build a route interactively (optionally with override / ToT)
baldrick.exe
baldrick.exe -c metric -t 12:35:00
```

### Selecting a config override

1. Define named blocks under `overrides:` in `config.yaml`.
2. Pass `-c <name>` (must match the override’s `name` field exactly).

Unknown override names fail with an error listing the available names.

### Selecting a route file

1. Place a YAML file in `routes/` (e.g. `routes/my_route.yaml`).
2. Pass the basename only: `-r my_route` (no path, no `.yaml`).

### Interactive route builder

Triggered when `--route` / `-r` is omitted. Prompts in the terminal:

1. **Route name**
2. For each waypoint:
   - Name
   - Tags (checkbox: `TGT`, `IP`, `FIX`, `PUSH`, `HOME`, `DIVERT`, `AAR`)
   - Position — MGRS, or latitude/longitude (DMS or DDM)
   - From the second waypoint onward (each optional): leg speed, altitude, fixed time (`HH:MM:SS`)
   - Notes
   - Whether to add another waypoint

Notes:

- The built route exists **only for that run** — it is not written to a YAML file. Save a route file yourself if you want to reuse it.
- FLOT is not available in the builder (use a route YAML).
- `--config`, `--tot`, and `--push` still apply when building interactively.
- If the route fits more than one base map and no `map:` is set, you will be asked which map to use.

On success the CLI prints bingo fuel and total fuel required when a fuel map is configured, any warnings, and the output folder path. On failure it prints `Error: …` and exits with code 1.

---

## Output

Each run creates (or recreates) `output/<route name>/` containing:

| File | Description |
|------|-------------|
| `<MAP>-00-Legend.jpg` | Symbol and doghouse field key |
| `<MAP>-01-Overview.jpg` | Whole-route overview with fuel summary |
| `<MAP>-02-wp01.jpg` … `<MAP>-02-wpNN.jpg` | One kneeboard per main-route leg (DIVERT waypoints excluded) |
| `<MAP>-03-divert-<name>.jpg` | One contingency card per DIVERT waypoint |
| `notes.txt` | Text summary: ETAs, speeds, ESA, min fuel, bingo/joker, warnings |
| `<route name>.zip` | Zip archive of the folder contents |

Cards are 1600×2400. Extension is `.jpg` when opaque, or `.png` when `card_alpha` is below 255.

Each leg card includes a cropped, rotated map section, route overlay (current leg solid, others faded), waypoint markers, and a doghouse block with WP name, magnetic course, distance, ETA (absolute and relative to push when applicable), ESA, TAS, min fuel, next magnetic course, fix coordinates, and notes.

---

## Appendix

### Common errors

Baldrick stops and prints `Error: …` for the following:

| Situation | Example |
|-----------|---------|
| Route file missing | `Route file not found: …/routes/my_route.yaml` |
| No map contains all waypoints | Lists each base map and which waypoints are out of bounds |
| Impossible ToT / speed constraints | Segment times cannot be satisfied with fixed-speed legs |
| Fuel map file missing | `Fuel map '…' not found … Omit or null 'fuel_map'…` |
| Route exceeds fuel capacity | Route fuel requirement exceeds map capacity after reserve |
| Unknown config override | Override name not found in `overrides` |

Invalid YAML, coordinates, timestamps, or fuel units may raise validation errors during file loading.

### Warnings

Warnings do **not** stop the run. They are printed in yellow and also included in `notes.txt`.

| Source | When |
|--------|------|
| ToT planner | No timed waypoints; default cruise speed used |
| ToT planner | `--tot` / `--push` given but no TGT / PUSH waypoint |
| Fuel calculator | No fuel map configured; leg outside map bounds; no HOME waypoint |
| ESA calculator | Missing min-altitude data for the map or a leg |

### Further reading

Detailed design notes live in `docs/`:

- [`docs/overview.md`](docs/overview.md) — functional overview
- [`docs/route_file_format.md`](docs/route_file_format.md) — route file reference
- [`docs/fuel_map_format.md`](docs/fuel_map_format.md) — fuel map reference
- [`docs/config_format`](docs/config_format) — config reference
- [`docs/architecture_notes.md`](docs/architecture_notes.md) — algorithms and error-handling design

### Building from source

For development or creating your own release bundle:

- Python 3.13+
- [uv](https://docs.astral.sh/uv/)

```bash
git clone <repo-url>
cd Baldrick_2
uv sync
uv run python src/baldrick.py -r example_route_file
uv run python build.py
```

The distributable is written to `dist/baldrick/` with `baldrick.exe`, `config.yaml`, `routes/`, and `fuel_maps/` beside the executable. Map data ships inside `_internal/`.
