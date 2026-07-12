from __future__ import annotations

from pathlib import Path

import yaml

from domain.config import Config, ConfigOverride
from parsing.fuel_map_loader import load_fuel_map
from shared import paths
from shared.errors import BaldrickError


def attach_fuel_map(conf: Config) -> None:
    """Load the configured fuel map, or leave fuel planning disabled."""
    if not conf.fuel_map:
        conf.active_fuel_map = None
        return
    fuel_map_path = paths.fuel_maps_dir() / f"{conf.fuel_map}.yaml"
    if not fuel_map_path.exists():
        raise BaldrickError(
            f"Fuel map '{conf.fuel_map}' not found at {fuel_map_path}. "
            f"Omit or null 'fuel_map' in config.yaml to skip fuel calculations."
        )
    conf.active_fuel_map = load_fuel_map(fuel_map_path)


def load_config(path: Path | None = None) -> Config:
    path = path or paths.config_path()
    with path.open("r", encoding="utf-8") as file:
        data = yaml.load(file, Loader=yaml.SafeLoader) or {}
    raw_overrides = data.pop("overrides", None) or []
    overrides = [ConfigOverride(**entry) for entry in raw_overrides]
    conf = Config(**data, overrides=overrides)
    attach_fuel_map(conf)
    return conf


def apply_override(conf: Config, override: str | None) -> Config:
    if override is None:
        return conf
    match = next((o for o in conf.overrides if o.name == override), None)
    if match is None:
        raise ValueError(
            f"Config override '{override}' not found. "
            f"Available: {[o.name for o in conf.overrides] or 'none'}"
        )
    result = conf.with_override(match)
    attach_fuel_map(result)
    return result
