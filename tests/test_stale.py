"""Tests for keeping the last values over isolated failed polls (#5)."""
import importlib.util
import unittest
from pathlib import Path

MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "keba_one_ev"
    / "stale.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("keba_stale", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestStaleTolerance(unittest.TestCase):
    def setUp(self):
        self.stale = load_module()

    def test_keeps_previous_data_for_isolated_failures(self):
        t = self.stale.StaleTolerance(max_stale=2)
        self.assertTrue(t.on_failure(has_previous=True))
        self.assertTrue(t.on_failure(has_previous=True))

    def test_gives_up_after_max_stale_failures(self):
        t = self.stale.StaleTolerance(max_stale=2)
        t.on_failure(has_previous=True)
        t.on_failure(has_previous=True)
        self.assertFalse(t.on_failure(has_previous=True))

    def test_success_resets_the_counter(self):
        t = self.stale.StaleTolerance(max_stale=2)
        t.on_failure(has_previous=True)
        t.on_failure(has_previous=True)
        t.on_success()
        self.assertTrue(t.on_failure(has_previous=True))

    def test_never_keeps_data_when_there_is_none(self):
        # First refresh: nothing to fall back on, setup must fail.
        t = self.stale.StaleTolerance(max_stale=2)
        self.assertFalse(t.on_failure(has_previous=False))


if __name__ == "__main__":
    unittest.main()
