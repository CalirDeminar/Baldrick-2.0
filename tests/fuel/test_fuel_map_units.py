import pytest

from fuel.fuel_map import FuelMap, consumption_to_lb_per_nm, to_lbs


class TestFuelUnitConversion:
    def test_kg_capacity(self, tmp_path):
        data = {
            "name": "METRIC",
            "capacity": 1000,
            "capacity_unit": "kg",
            "fuelMap": [
                {"altitude_ft": 0, "speed_kts": 300, "lb_per_nm": 30.0},
            ],
        }
        path = tmp_path / "metric.yaml"
        path.write_text(
            "name: METRIC\ncapacity: 1000\ncapacity_unit: kg\nfuelMap:\n"
            "  - {altitude_ft: 0, speed_kts: 300, lb_per_nm: 30.0}\n"
        )
        fm = FuelMap.from_file(path)
        assert fm.capacity == pytest.approx(int(round(to_lbs(1000, "kg"))))

    def test_consumption_per_km(self):
        # 10 kg/km at 300 kts -> convert to lb/nm
        expected = consumption_to_lb_per_nm(
            10,
            volume_unit="kg",
            speed_kts=300,
            distance_unit="km",
        )
        assert expected == pytest.approx(10 * 2.20462 * 1.852)

    def test_consumption_per_hour(self):
        # 1200 lb/hr at 300 kts -> 4 lb/nm
        expected = consumption_to_lb_per_nm(
            1200,
            volume_unit="lb",
            speed_kts=300,
            time_unit="hr",
        )
        assert expected == pytest.approx(4.0)

    def test_consumption_per_minute(self):
        # 20 lb/min at 300 kts -> 4 lb/nm
        expected = consumption_to_lb_per_nm(
            20,
            volume_unit="lb",
            speed_kts=300,
            time_unit="min",
        )
        assert expected == pytest.approx(4.0)

    def test_gallons_per_nm(self, tmp_path):
        path = tmp_path / "gal.yaml"
        path.write_text(
            "name: GALTEST\n"
            "capacity: 100\n"
            "capacity_unit: gal\n"
            "fuelMap:\n"
            "  - altitude_ft: 0\n"
            "    speed_kts: 300\n"
            "    consumption: 4\n"
            "    consumption_volume_unit: gal\n"
            "    consumption_distance_unit: nm\n"
        )
        fm = FuelMap.from_file(path)
        cell = fm.fuel_map_by_altitude[0].map_by_speed[300]
        assert cell.fuel_lbs_per_nm == pytest.approx(4 * 6.7)
