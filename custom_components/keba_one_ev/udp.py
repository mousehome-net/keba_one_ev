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
"""
from __future__ import annotations

import json
import logging
import socket
import threading

_LOGGER = logging.getLogger(__name__)

_SOCKET_LOCK = threading.Lock()


def send_command(host: str, port: int, command: str, timeout: float = 3.0) -> dict | None:
    """Send one KEBA UDP command and return the parsed JSON response.

    Opens a fresh socket per call (the protocol is stateless), bound to
    the charger port so the reply can actually be received. Returns None
    on timeout or any other error so callers can handle missing data
    gracefully.
    """
    with _SOCKET_LOCK:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("", port))
        sock.settimeout(timeout)
        try:
            sock.sendto(command.encode(), (host, port))
            data, _ = sock.recvfrom(4096)
            text = data.decode()
            # Control commands (ena, curr, setenergy, ...) are acknowledged
            # with plain text, not JSON -- issue #10. Only "report" replies
            # are JSON.
            if text.startswith("TCH-OK"):
                return {}
            return json.loads(text)
        except socket.timeout:
            _LOGGER.warning("Timeout sending '%s' to %s:%s", command, host, port)
            return None
        except Exception as err:
            _LOGGER.error("Error sending '%s' to %s:%s: %s", command, host, port, err)
            return None
        finally:
            sock.close()
