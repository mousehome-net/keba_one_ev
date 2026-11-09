"""Tests for session duration derivation (issue #6).

Loaded by file path so this has no dependency on homeassistant.
"""
import importlib.util
import unittest
from pathlib import Path

MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "keba_one_ev"
    / "session.py"
)


def load_session_module():
    spec = importlib.util.spec_from_file_location("keba_session", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestSessionDurationS(unittest.TestCase):
    def setUp(self):
        self.session = load_session_module()

    def test_no_session_started_yet(self):
        self.assertEqual(self.session.session_duration_s(started=0, ended=0, now=1793541598), 0)

    def test_ongoing_session_uses_now(self):
        # Real values from the live charger: session started at
        # 1793530245, queried "now" at 1793541598 -> ~3h09m elapsed.
        self.assertEqual(
            self.session.session_duration_s(started=1793530245, ended=0, now=1793541598),
            11353,
        )

    def test_finished_session_uses_ended_not_now(self):
        self.assertEqual(
            self.session.session_duration_s(started=1000, ended=1050, now=999999),
            50,
        )

    def test_never_negative(self):
        # Defensive: clock skew between charger and HA host should not
        # produce a negative duration.
        self.assertEqual(self.session.session_duration_s(started=1050, ended=0, now=1000), 0)


class TestSessionStartDatetime(unittest.TestCase):
    def setUp(self):
        self.session = load_session_module()

    def test_no_session_means_no_start(self):
        self.assertIsNone(self.session.session_start_datetime(0))

    def test_epoch_is_converted_to_utc(self):
        # Real report 100 of the maintainer's charger:
        # "started[s]": 1794220448, "started": "2026-11-09 10:34:08.797Z"
        from datetime import datetime, timezone
        self.assertEqual(
            self.session.session_start_datetime(1794220448),
            datetime(2026, 11, 9, 10, 34, 8, tzinfo=timezone.utc),
        )


if __name__ == "__main__":
    unittest.main()
