"""Low-level UDP transport for the KEBA protocol.

KEBA chargers always reply to source port 7090, regardless of which local
port the request came from. The local socket must therefore be bound to
that port before sending, or the reply goes to an ephemeral port nothing
is listening on (this is harmless on some bare-metal setups but always
breaks when Home Assistant runs in Docker with bridge networking -- see
issue #7).

Port 7090 is a single local resource shared by every KebaCoordinator in
the process (one per configured charger) and by the config flow's
connection test, so only one exchange may be in flight at a time -- hence
the module-level lock.

KEBA also requires at least 100 ms between any two commands (t_UDP_pause),
and the charger may push status messages (KEBA guide 4.4) or answer late, so
a reply is only accepted if it belongs to the command that was sent.
"""
from __future__ import annotations

import json
import logging
import socket
import threading
import time

_LOGGER = logging.getLogger(__name__)

_SOCKET_LOCK = threading.Lock()

_MIN_GAP_S = 0.1
_last_exchange_end = 0.0


def _report_id(command: str) -> str | None:
    """'report 2' -> '2'; None for anything that is not a report."""
    parts = command.split()
    if len(parts) == 2 and parts[0] == "report":
        return parts[1]
    return None


def _accept(command: str, text: str) -> tuple[bool, dict | None]:
    """Decide whether a datagram is the reply to `command`.

    Returns (accepted, value). Not accepted means: keep waiting.
    """
    report = _report_id(command)
    if report is None:
        # Control commands (curr, setenergy, ...) are acknowledged with
        # plain text, not JSON -- issue #10. Some firmwares answer ena /
        # xswitchphase with an empty datagram -- issue #12.
        if text.startswith("TCH-OK") or not text.strip():
            return True, {}
        if text.lstrip().startswith("{"):
            return False, None  # a pushed status message, not our reply
        return True, json.loads(text)
    reply = json.loads(text)
    if str(reply.get("ID")) != report:
        return False, None  # another report or a status push
    return True, reply


def send_command(host: str, port: int, command: str, timeout: float = 3.0) -> dict | None:
    """Send one KEBA UDP command and return the parsed JSON response.

    Opens a fresh socket per call (the protocol is stateless), bound to
    the charger port so the reply can actually be received. Returns None
    on timeout or any other error so callers can handle missing data
    gracefully.
    """
    global _last_exchange_end
    with _SOCKET_LOCK:
        wait = _MIN_GAP_S - (time.monotonic() - _last_exchange_end)
        if wait > 0:
            time.sleep(wait)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("", port))
        sock.settimeout(timeout)
        try:
            sock.sendto(command.encode(), (host, port))
            deadline = time.monotonic() + timeout
            while True:
                data, _ = sock.recvfrom(4096)
                accepted, value = _accept(command, data.decode())
                if accepted:
                    return value
                _LOGGER.debug("Ignoring unrelated datagram while waiting for '%s'", command)
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise socket.timeout
                sock.settimeout(remaining)
        except socket.timeout:
            # A single dropped UDP packet is routine on this protocol and is
            # already handled by the retry in fetch.py -- logging it above
            # DEBUG would flood HA's "repeated issues" view for something
            # that self-heals (see issue #11).
            _LOGGER.debug("Timeout sending '%s' to %s:%s", command, host, port)
            return None
        except Exception as err:
            _LOGGER.error("Error sending '%s' to %s:%s: %s", command, host, port, err)
            return None
        finally:
            sock.close()
            _last_exchange_end = time.monotonic()
