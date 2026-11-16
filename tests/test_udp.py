"""Tests for the low-level KEBA UDP transport (issue #7).

Loaded by file path, not by package import, so this module has no
dependency on homeassistant being installed -- it only touches
json/logging/socket/threading.
"""
import importlib.util
import json
import socket
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "keba_one_ev"
    / "udp.py"
)


def load_udp_module():
    spec = importlib.util.spec_from_file_location("keba_udp", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestSendCommandBinding(unittest.TestCase):
    """The socket must be bound to the charger port before sendto()."""

    def setUp(self):
        self.udp = load_udp_module()

    def test_binds_to_charger_port_before_sending(self):
        mock_sock = MagicMock()
        mock_sock.recvfrom.return_value = (b'{"ID": 1, "Product": "ONE_EV"}', ("10.0.0.5", 7090))

        with patch.object(self.udp.socket, "socket", return_value=mock_sock) as mock_socket_cls:
            result = self.udp.send_command("10.0.0.5", 7090, "report 1")

        mock_socket_cls.assert_called_once_with(socket.AF_INET, socket.SOCK_DGRAM)
        mock_sock.setsockopt.assert_called_once_with(
            socket.SOL_SOCKET, socket.SO_REUSEADDR, 1
        )
        mock_sock.bind.assert_called_once_with(("", 7090))

        # bind() must happen before sendto(), otherwise the OS has already
        # picked an ephemeral source port and the fix is a no-op.
        bind_call_index = mock_sock.method_calls.index(unittest.mock.call.bind(("", 7090)))
        sendto_call_index = next(
            i for i, c in enumerate(mock_sock.method_calls) if c[0] == "sendto"
        )
        self.assertLess(bind_call_index, sendto_call_index)

        self.assertEqual(result, {"ID": 1, "Product": "ONE_EV"})
        mock_sock.close.assert_called_once()

    def test_returns_none_on_timeout(self):
        mock_sock = MagicMock()
        mock_sock.recvfrom.side_effect = socket.timeout

        with patch.object(self.udp.socket, "socket", return_value=mock_sock):
            result = self.udp.send_command("10.0.0.5", 7090, "report 1", timeout=0.01)

        self.assertIsNone(result)
        mock_sock.close.assert_called_once()

    def test_timeout_does_not_log_above_debug(self):
        # A single dropped UDP packet is routine and already handled by
        # the retry in fetch.py -- it must not reach WARNING and flood
        # HA's "repeated issues" view (issue #11).
        mock_sock = MagicMock()
        mock_sock.recvfrom.side_effect = socket.timeout

        with patch.object(self.udp.socket, "socket", return_value=mock_sock):
            with self.assertNoLogs(self.udp._LOGGER.name, level="INFO"):
                self.udp.send_command("10.0.0.5", 7090, "report 1", timeout=0.01)

    def test_tch_ok_acknowledgement_is_treated_as_success(self):
        # Control commands (ena, curr, setenergy, ...) reply with the
        # plain-text "TCH-OK: done", not JSON -- issue #10.
        mock_sock = MagicMock()
        mock_sock.recvfrom.return_value = (b"TCH-OK: done", ("10.0.0.5", 7090))

        with patch.object(self.udp.socket, "socket", return_value=mock_sock):
            result = self.udp.send_command("10.0.0.5", 7090, "curr 11000")

        self.assertIsNotNone(result)

    def test_empty_reply_to_control_command_is_treated_as_success(self):
        # ena / xswitchphase answer with an empty datagram on some
        # firmwares -- issue #12.
        for command in ("ena 0", "xswitchphase 1"):
            mock_sock = MagicMock()
            mock_sock.recvfrom.return_value = (b"", ("10.0.0.5", 7090))

            with patch.object(self.udp.socket, "socket", return_value=mock_sock):
                result = self.udp.send_command("10.0.0.5", 7090, command)

            self.assertIsNotNone(result, command)

    def test_empty_reply_to_report_is_still_a_failure(self):
        mock_sock = MagicMock()
        mock_sock.recvfrom.return_value = (b"", ("10.0.0.5", 7090))

        with patch.object(self.udp.socket, "socket", return_value=mock_sock):
            with self.assertLogs(self.udp._LOGGER, level="ERROR"):
                result = self.udp.send_command("10.0.0.5", 7090, "report 2")

        self.assertIsNone(result)

    def test_returns_none_on_malformed_json(self):
        mock_sock = MagicMock()
        mock_sock.recvfrom.return_value = (b"not json", ("10.0.0.5", 7090))

        with patch.object(self.udp.socket, "socket", return_value=mock_sock):
            result = self.udp.send_command("10.0.0.5", 7090, "report 1")

        self.assertIsNone(result)


class TestReplyMatching(unittest.TestCase):
    """Only the reply to the requested report counts: the charger can push
    status messages (KEBA guide 4.4) and late replies can arrive."""

    def setUp(self):
        self.udp = load_udp_module()

    def _send(self, command, datagrams):
        mock_sock = MagicMock()
        mock_sock.recvfrom.side_effect = [(d, ("10.0.0.5", 7090)) for d in datagrams] + [socket.timeout]
        with patch.object(self.udp.socket, "socket", return_value=mock_sock):
            return self.udp.send_command("10.0.0.5", 7090, command, timeout=0.5)

    def test_reply_with_other_report_id_is_skipped(self):
        result = self._send("report 2", [b'{"ID":3,"P":1}', b'{"ID":2,"State":3}'])
        self.assertEqual(result, {"ID": 2, "State": 3})

    def test_status_push_without_id_is_skipped(self):
        result = self._send("report 2", [b'{"State":3}', b'{"ID":2,"State":3}'])
        self.assertEqual(result, {"ID": 2, "State": 3})

    def test_string_id_is_accepted(self):
        # A genuine P30 (#5) sends "ID": "1"
        result = self._send("report 1", [b'{"ID":"1","Product":"KC-P30"}'])
        self.assertEqual(result["Product"], "KC-P30")

    def test_only_wrong_replies_means_none(self):
        self.assertIsNone(self._send("report 2", [b'{"ID":3}']))

    def test_status_push_before_control_ack_is_skipped(self):
        self.assertEqual(self._send("curr 10000", [b'{"Max curr":10000}', b"TCH-OK: done"]), {})


class TestMinimumGap(unittest.TestCase):
    """KEBA requires at least 100 ms between any two commands (t_UDP_pause)."""

    def test_waits_for_the_remaining_gap(self):
        udp = load_udp_module()
        mock_sock = MagicMock()
        mock_sock.recvfrom.return_value = (b"TCH-OK: done", ("10.0.0.5", 7090))
        udp._last_exchange_end = 100.0
        with patch.object(udp.socket, "socket", return_value=mock_sock), \
             patch.object(udp.time, "monotonic", return_value=100.03), \
             patch.object(udp.time, "sleep") as fake_sleep:
            udp.send_command("10.0.0.5", 7090, "curr 10000")
        fake_sleep.assert_called_once()
        self.assertAlmostEqual(fake_sleep.call_args[0][0], 0.07, places=3)

    def test_no_wait_when_the_gap_has_passed(self):
        udp = load_udp_module()
        mock_sock = MagicMock()
        mock_sock.recvfrom.return_value = (b"TCH-OK: done", ("10.0.0.5", 7090))
        udp._last_exchange_end = 100.0
        with patch.object(udp.socket, "socket", return_value=mock_sock), \
             patch.object(udp.time, "monotonic", return_value=101.0), \
             patch.object(udp.time, "sleep") as fake_sleep:
            udp.send_command("10.0.0.5", 7090, "curr 10000")
        fake_sleep.assert_not_called()


class TestSendCommandSerialization(unittest.TestCase):
    """Only one exchange may be in flight at a time: port 7090 is a single
    shared local resource, even across multiple charger coordinators."""

    def test_concurrent_calls_are_serialized(self):
        udp = load_udp_module()
        in_flight = threading.Event()
        overlap_detected = threading.Event()

        def tracking_bind(address):
            if in_flight.is_set():
                overlap_detected.set()
            in_flight.set()
            time.sleep(0.05)
            in_flight.clear()

        mock_sock_factory_calls = []

        def make_socket(*args, **kwargs):
            s = MagicMock()
            def reply(*_args):
                cmd = s.sendto.call_args[0][0].decode()
                body = b'{"ID": 2}' if cmd == "report 2" else b"TCH-OK: done"
                return (body, ("10.0.0.5", 7090))

            s.recvfrom.side_effect = reply
            s.bind.side_effect = tracking_bind
            mock_sock_factory_calls.append(s)
            return s

        with patch.object(udp.socket, "socket", side_effect=make_socket):
            t1 = threading.Thread(target=udp.send_command, args=("10.0.0.5", 7090, "report 2"))
            t2 = threading.Thread(target=udp.send_command, args=("10.0.0.5", 7090, "curr 11000"))
            t1.start()
            t2.start()
            t1.join()
            t2.join()

        self.assertFalse(
            overlap_detected.is_set(),
            "two UDP exchanges on port 7090 overlapped -- the lock did not serialize them",
        )


if __name__ == "__main__":
    unittest.main()
