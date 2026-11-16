"""Tests for the charging-current range taken from Curr HW (#3)."""
import importlib.util
import unittest
from pathlib import Path

MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "keba_one_ev"
    / "limits.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("keba_limits", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestMaxCurrent(unittest.TestCase):
    def setUp(self):
        self.limits = load_module()

    def test_uses_curr_hw(self):
        # Real values: 16000 on the maintainer's unit, 32000 in #3
        self.assertEqual(self.limits.max_current_ma(16000), 16000)
        self.assertEqual(self.limits.max_current_ma(32000), 32000)

    def test_falls_back_when_curr_hw_is_missing_or_invalid(self):
        # The KEBA guide allows Curr HW = 0
        for value in (0, None, 3000, 40000):
            self.assertEqual(self.limits.max_current_ma(value), 16000, value)


class TestClampCurrent(unittest.TestCase):
    def setUp(self):
        self.limits = load_module()

    def test_clamps_to_the_hardware_limit(self):
        self.assertEqual(self.limits.clamp_current_ma(20000, 16000), 16000)
        self.assertEqual(self.limits.clamp_current_ma(20000, 32000), 20000)

    def test_never_below_6_a(self):
        self.assertEqual(self.limits.clamp_current_ma(4000, 32000), 6000)


if __name__ == "__main__":
    unittest.main()
