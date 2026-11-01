"""Tests for the polling sequence (issue #8: entities flap to Unavailable).

Loaded by file path so this has no dependency on homeassistant.
"""
import importlib.util
import unittest
from pathlib import Path
from unittest.mock import call

MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "keba_one_ev"
    / "fetch.py"
)


def load_fetch_module():
    spec = importlib.util.spec_from_file_location("keba_fetch", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeSend:
    """Records calls and returns scripted replies per command."""

    def __init__(self, replies: dict[str, list]):
        self.replies = {k: list(v) for k, v in replies.items()}
        self.calls = []

    def __call__(self, command):
        self.calls.append(command)
        queue = self.replies.get(command, [])
        return queue.pop(0) if queue else None


class TestFetchAll(unittest.TestCase):
    def setUp(self):
        self.fetch = load_fetch_module()
        self.sleeps = []

    def _sleep(self, seconds):
        self.sleeps.append(seconds)

    def test_pauses_between_every_report(self):
        send = FakeSend({
            "report 1": [{"Product": "ONE_EV"}],
            "report 2": [{"State": 2}],
            "report 3": [{"P": 100}],
            "report 100": [{"Session ID": 1}],
        })

        self.fetch.fetch_all(send, sleep=self._sleep)

        self.assertEqual(send.calls, ["report 1", "report 2", "report 3", "report 100"])
        self.assertEqual(len(self.sleeps), 3)
        self.assertTrue(all(s > 0 for s in self.sleeps))

    def test_mandatory_report_is_retried_once_on_failure(self):
        send = FakeSend({
            "report 1": [{"Product": "ONE_EV"}],
            "report 2": [None, {"State": 2}],  # dropped once, then succeeds
            "report 3": [{"P": 100}],
            "report 100": [{"Session ID": 1}],
        })

        r1, r2, r3, r100 = self.fetch.fetch_all(send, sleep=self._sleep)

        self.assertEqual(r2, {"State": 2})
        self.assertEqual(send.calls.count("report 2"), 2)

    def test_mandatory_report_returns_none_if_retry_also_fails(self):
        send = FakeSend({
            "report 1": [{"Product": "ONE_EV"}],
            "report 2": [None, None],
            "report 3": [{"P": 100}],
            "report 100": [{"Session ID": 1}],
        })

        r1, r2, r3, r100 = self.fetch.fetch_all(send, sleep=self._sleep)

        self.assertIsNone(r2)
        self.assertEqual(send.calls.count("report 2"), 2)

    def test_optional_reports_are_not_retried(self):
        send = FakeSend({
            "report 1": [None],
            "report 2": [{"State": 2}],
            "report 3": [{"P": 100}],
            "report 100": [None],
        })

        r1, r2, r3, r100 = self.fetch.fetch_all(send, sleep=self._sleep)

        self.assertIsNone(r1)
        self.assertIsNone(r100)
        self.assertEqual(send.calls.count("report 1"), 1)
        self.assertEqual(send.calls.count("report 100"), 1)


if __name__ == "__main__":
    unittest.main()
