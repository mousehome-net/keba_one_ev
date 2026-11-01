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
        mock_sock.recvfrom.return_value = (b'{"Product": "ONE_EV"}', ("10.0.0.5", 7090))

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

        self.assertEqual(result, {"Product": "ONE_EV"})
        mock_sock.close.assert_called_once()

    def test_returns_none_on_timeout(self):
        mock_sock = MagicMock()
        mock_sock.recvfrom.side_effect = socket.timeout

        with patch.object(self.udp.socket, "socket", return_value=mock_sock):
            result = self.udp.send_command("10.0.0.5", 7090, "report 1", timeout=0.01)

        self.assertIsNone(result)
        mock_sock.close.assert_called_once()

    def test_tch_ok_acknowledgement_is_treated_as_success(self):
        # Control commands (ena, curr, setenergy, ...) reply with the
        # plain-text "TCH-OK: done", not JSON -- issue #10.
        mock_sock = MagicMock()
        mock_sock.recvfrom.return_value = (b"TCH-OK: done", ("10.0.0.5", 7090))

        with patch.object(self.udp.socket, "socket", return_value=mock_sock):
            result = self.udp.send_command("10.0.0.5", 7090, "curr 11000")

        self.assertIsNotNone(result)

    def test_returns_none_on_malformed_json(self):
        mock_sock = MagicMock()
        mock_sock.recvfrom.return_value = (b"not json", ("10.0.0.5", 7090))

        with patch.object(self.udp.socket, "socket", return_value=mock_sock):
            result = self.udp.send_command("10.0.0.5", 7090, "report 1")

        self.assertIsNone(result)


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
            s.recvfrom.return_value = (b'{"ok": true}', ("10.0.0.5", 7090))
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
