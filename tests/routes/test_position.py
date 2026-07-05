"""Tests for coordinate parsing."""

import pytest

from routes.position import DMSDistance, Position, parse_coordinate, parse_position


class TestDMSParsing:
    def test_comma_separated(self):
        parsed = parse_coordinate("49, 26, 30", kind="lat")
        assert parsed.to_decimal() == pytest.approx(49.4416666667)

    def test_space_separated(self):
        parsed = parse_coordinate("49 26 30", kind="lon")
        assert parsed.to_decimal() == pytest.approx(49.4416666667)


class TestDDMParsing:
    def test_decimal_minutes(self):
        parsed = parse_coordinate("51 30.5", kind="lat")
        assert parsed.to_decimal() == pytest.approx(51.5083333333)

    def test_hemisphere_prefix(self):
        parsed = parse_coordinate("N51 30.5", kind="lat")
        assert parsed.to_decimal() == pytest.approx(51.5083333333)

    def test_hemisphere_suffix(self):
        parsed = parse_coordinate("10 30.0 E", kind="lon")
        assert parsed.to_decimal() == pytest.approx(10.5)


class TestMGRSParsing:
    def test_mgrs_field(self):
        position = parse_position(mgrs_value="32U MV 12345 67890")
        lat, lon = position.to_decimal()
        assert -90 <= lat <= 90
        assert -180 <= lon <= 180

    def test_mgrs_in_lat_field(self):
        position = parse_position(lat="32U MV 12345 67890", lon=None)
        lat, lon = position.to_decimal()
        assert -90 <= lat <= 90
        assert -180 <= lon <= 180


class TestDecimalRoundTrip:
    def test_from_decimal(self):
        dms = DMSDistance.from_decimal(12.5)
        assert dms.to_decimal() == pytest.approx(12.5)

    def test_position_from_decimal(self):
        position = Position.from_decimal(12.5, -10.25)
        assert position.to_decimal() == (pytest.approx(12.5), pytest.approx(-10.25))
