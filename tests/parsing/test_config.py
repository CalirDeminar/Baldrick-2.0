from domain.config import Config, ConfigOverride
from parsing.config_loader import apply_override, attach_fuel_map
from shared.units import DistanceUnit


def _base_conf(**kw) -> Config:
    defaults = dict(
        min_cruise_speed=300,
        default_cruise_speed=420,
        dash_speed=540,
        units=DistanceUnit.NAUTICAL,
        fuel_map="example_fuel_map",
    )
    defaults.update(kw)
    return Config(**defaults)


class TestFuelMapOptional:
    def test_blank_fuel_map_normalizes_to_none(self):
        conf = _base_conf(fuel_map="  ")
        assert conf.fuel_map is None

    def test_null_fuel_map_skips_attach(self):
        conf = _base_conf(fuel_map=None)
        attach_fuel_map(conf)
        assert conf.active_fuel_map is None

    def test_override_can_clear_fuel_map(self):
        # Simulate YAML that explicitly set fuel_map: null
        override = ConfigOverride.model_validate({"name": "no_fuel", "fuel_map": None})
        conf = Config(
            min_cruise_speed=300,
            default_cruise_speed=420,
            dash_speed=540,
            fuel_map="example_fuel_map",
            overrides=[override],
        )
        result = apply_override(conf, "no_fuel")
        assert result.fuel_map is None
        assert result.active_fuel_map is None

    def test_override_blank_fuel_map_clears(self):
        override = ConfigOverride.model_validate({"name": "no_fuel", "fuel_map": ""})
        conf = Config(
            min_cruise_speed=300,
            default_cruise_speed=420,
            dash_speed=540,
            fuel_map="example_fuel_map",
            overrides=[override],
        )
        result = apply_override(conf, "no_fuel")
        assert result.fuel_map is None
        assert result.active_fuel_map is None

    def test_omitted_override_fuel_map_keeps_base(self):
        override = ConfigOverride.model_validate(
            {"name": "warbirds", "min_cruise_speed": 220}
        )
        conf = Config(
            min_cruise_speed=300,
            default_cruise_speed=420,
            dash_speed=540,
            fuel_map="example_fuel_map",
            overrides=[override],
        )
        result = conf.with_override(override)
        assert result.fuel_map == "example_fuel_map"
        assert result.min_cruise_speed == 220

    def test_null_override_does_not_clear_other_fields(self):
        override = ConfigOverride.model_validate(
            {"name": "partial", "takeoff_fuel": None, "min_cruise_speed": 200}
        )
        conf = Config(
            min_cruise_speed=300,
            default_cruise_speed=420,
            dash_speed=540,
            takeoff_fuel=2500,
            overrides=[override],
        )
        result = conf.with_override(override)
        assert result.takeoff_fuel == 2500
        assert result.min_cruise_speed == 200
