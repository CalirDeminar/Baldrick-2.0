from pydantic import ValidationError
import pytest

from domain.config import Config, ConfigOverride, effective_card_alpha
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


class TestCardAlpha:
    def test_omitted_card_alpha_is_none(self):
        conf = _base_conf()
        assert conf.card_alpha is None
        assert effective_card_alpha(conf) == 255

    def test_null_card_alpha_resolves_to_opaque(self):
        conf = _base_conf(card_alpha=None)
        assert effective_card_alpha(conf) == 255

    def test_explicit_card_alpha_is_used(self):
        conf = _base_conf(card_alpha=180)
        assert effective_card_alpha(conf) == 180

    def test_override_can_set_card_alpha(self):
        override = ConfigOverride.model_validate({"name": "transparent", "card_alpha": 128})
        conf = Config(
            min_cruise_speed=300,
            default_cruise_speed=420,
            dash_speed=540,
            overrides=[override],
        )
        result = conf.with_override(override)
        assert result.card_alpha == 128
        assert effective_card_alpha(result) == 128

    def test_override_can_clear_card_alpha_to_opaque(self):
        override = ConfigOverride.model_validate({"name": "opaque", "card_alpha": None})
        conf = Config(
            min_cruise_speed=300,
            default_cruise_speed=420,
            dash_speed=540,
            card_alpha=128,
            overrides=[override],
        )
        result = conf.with_override(override)
        assert result.card_alpha is None
        assert effective_card_alpha(result) == 255


class TestFadedLegAlpha:
    def test_omitted_faded_leg_alpha_defaults_to_150(self):
        conf = _base_conf()
        assert conf.faded_leg_alpha == 150

    def test_explicit_faded_leg_alpha_is_used(self):
        conf = _base_conf(faded_leg_alpha=50)
        assert conf.faded_leg_alpha == 50

    def test_override_can_set_faded_leg_alpha(self):
        override = ConfigOverride.model_validate({"name": "faint", "faded_leg_alpha": 40})
        conf = Config(
            min_cruise_speed=300,
            default_cruise_speed=420,
            dash_speed=540,
            overrides=[override],
        )
        result = conf.with_override(override)
        assert result.faded_leg_alpha == 40

    def test_faded_leg_alpha_out_of_range_rejected(self):
        with pytest.raises(ValidationError):
            _base_conf(faded_leg_alpha=300)
