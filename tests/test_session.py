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


class TestGenuineP30Semantics(unittest.TestCase):
    """KEBA's guide: started[s]/ended[s] are seconds since the charger's last
    restart (the SolarEdge ONE sends Unix time instead)."""

    def setUp(self):
        self.session = load_session_module()

    def test_duration_from_uptime_while_running(self):
        # started 1000 s after boot, the charger now reports Sec = 4600
        self.assertEqual(
            self.session.session_duration_s(started=1000, ended=0, now=1794220448, uptime=4600),
            3600,
        )

    def test_duration_from_uptime_when_finished(self):
        self.assertEqual(
            self.session.session_duration_s(started=1000, ended=2800, now=1794220448, uptime=9999),
            1800,
        )

    def test_epoch_values_still_use_now(self):
        self.assertEqual(
            self.session.session_duration_s(started=1794220448, ended=0, now=1794224048, uptime=715218),
            3600,
        )

    def test_start_time_from_text_when_seconds_are_uptime(self):
        from datetime import datetime, timezone
        self.assertEqual(
            self.session.session_start_datetime(1000, "2026-11-05 12:16:13.853Z"),
            datetime(2026, 11, 5, 12, 16, 13, 853000, tzinfo=timezone.utc),
        )

    def test_no_start_time_without_a_real_date(self):
        # Without NTP the text holds the same uptime value as started[s]
        self.assertIsNone(self.session.session_start_datetime(1000, "1000"))
        self.assertIsNone(self.session.session_start_datetime(1000, ""))


class TestLastSession(unittest.TestCase):
    def setUp(self):
        self.session = load_session_module()

    def test_needs_history_only_when_the_session_changed(self):
        self.assertTrue(self.session.needs_history(current_id=5, fetched_for=None))
        self.assertTrue(self.session.needs_history(current_id=6, fetched_for=5))
        self.assertFalse(self.session.needs_history(current_id=5, fetched_for=5))
        self.assertFalse(self.session.needs_history(current_id=None, fetched_for=None))

    def test_summary_from_real_report_101(self):
        from datetime import datetime, timezone
        r101 = {"ID": 101, "Session ID": 4, "E Pres": 103759,
                "started[s]": 1794220448, "ended[s]": 1794225102,
                "started": "2026-11-09 10:34:08.797Z", "ended": "2026-11-09 11:51:42.042Z", "reason": 1}
        s = self.session.last_session_summary(r101)
        self.assertEqual(s["energy_kwh"], 10.38)
        self.assertEqual(s["duration_s"], 4654)
        self.assertEqual(s["started"], datetime(2026, 11, 9, 10, 34, 8, tzinfo=timezone.utc))
        self.assertEqual(s["ended"], datetime(2026, 11, 9, 11, 51, 42, tzinfo=timezone.utc))

    def test_summary_of_an_empty_entry(self):
        s = self.session.last_session_summary({"ID": 101, "E Pres": 0, "started[s]": 0, "ended[s]": 0})
        self.assertIsNone(s["started"])
        self.assertIsNone(s["duration_s"])

    def test_no_report_means_no_summary(self):
        self.assertIsNone(self.session.last_session_summary(None))


if __name__ == "__main__":
    unittest.main()
