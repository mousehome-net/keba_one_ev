"""Tests for reading the active phase mode (replaces the phase selector)."""
import importlib.util
import unittest
from pathlib import Path

MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "keba_one_ev"
    / "phase.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("keba_phase", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestPhaseMode(unittest.TestCase):
    def setUp(self):
        self.phase = load_module()

    def test_three_phases(self):
        self.assertEqual(self.phase.phase_mode(3), "3_phase")

    def test_one_phase(self):
        # Seen on the maintainer's charger after switching in the SolarEdge app.
        self.assertEqual(self.phase.phase_mode(1), "1_phase")

    def test_two_phases_are_reported_as_one(self):
        # Some hardware variants report 2; treated as single-phase.
        self.assertEqual(self.phase.phase_mode(2), "1_phase")

    def test_unknown_values_are_none(self):
        # 0 on a single-phase unit without a phase switch (issue #5).
        self.assertIsNone(self.phase.phase_mode(0))
        self.assertIsNone(self.phase.phase_mode(None))

    def test_options_match_what_is_returned(self):
        for value in (1, 2, 3):
            self.assertIn(self.phase.phase_mode(value), self.phase.PHASE_OPTIONS)


if __name__ == "__main__":
    unittest.main()
