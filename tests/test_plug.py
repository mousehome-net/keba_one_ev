"""Tests for KEBA Plug bitmask interpretation (issue #4).

Loaded by file path so this has no dependency on homeassistant being
installed.
"""
import importlib.util
import unittest
from pathlib import Path

MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "keba_one_ev"
    / "plug.py"
)


def load_plug_module():
    spec = importlib.util.spec_from_file_location("keba_plug", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestIsVehicleConnected(unittest.TestCase):
    """Only bit 2 (cable in the vehicle) means a vehicle is actually there."""

    def setUp(self):
        self.plug = load_plug_module()

    def test_no_cable(self):
        self.assertFalse(self.plug.is_vehicle_connected(0))

    def test_cable_in_station_only(self):
        # The false-positive from issue #4: cable plugged into the
        # wallbox, nothing plugged into the car.
        self.assertFalse(self.plug.is_vehicle_connected(1))

    def test_cable_in_station_and_locked(self):
        self.assertFalse(self.plug.is_vehicle_connected(3))

    def test_cable_in_vehicle(self):
        self.assertTrue(self.plug.is_vehicle_connected(5))

    def test_cable_in_vehicle_and_locked(self):
        self.assertTrue(self.plug.is_vehicle_connected(7))

    def test_missing_value_treated_as_no_cable(self):
        self.assertFalse(self.plug.is_vehicle_connected(None))


if __name__ == "__main__":
    unittest.main()
