"""DataUpdateCoordinator for the SE One EV Charger integration.

The coordinator is the single point of contact with the physical charger.
It runs a timed polling loop (default: every 10 s) and fetches all four KEBA
UDP reports in one go. All entity platforms (sensor, switch, number, select)
subscribe to the coordinator instead of opening their own sockets.

KEBA UDP protocol summary
--------------------------
Transport : UDP unicast, charger listens on port 7090
Direction : request → response (no unsolicited pushes)
Encoding  : request = plain-text ASCII, response = JSON

Reports used:
  report 1   → product / serial / firmware (device identity)
  report 2   → charging state, enable flags, current limits, phase mode
  report 3   → live measurements: voltage, current, power, energy
  report 100 → OCPP session data: RFID tag, session start/end timestamps

Unit conventions in the raw KEBA data:
  Currents  : milliamperes  (divide by 1000 for A)
  Power     : milliwatts    (divide by 1000 for W)
  Energy    : 0.1 Wh units  (multiply by 0.1 for Wh, or ×0.0001 for kWh)
  Voltage   : volts         (no conversion needed)
"""
from __future__ import annotations

import json
import logging
import socket
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class KebaCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Central data coordinator for the KEBA ONE EV charger.

    Inherits from DataUpdateCoordinator so Home Assistant handles the polling
    schedule, error throttling, and listener notification automatically.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        port: int,
        scan_interval: int = DEFAULT_SCAN_INTERVAL,
    ) -> None:
        self.host = host
        self.port = port
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )

    # ------------------------------------------------------------------
    # Low-level UDP communication
    # ------------------------------------------------------------------

    def _send(self, command: str, timeout: float = 3.0) -> dict | None:
        """Send a single KEBA UDP command and return the parsed JSON response.

        Opens a fresh UDP socket for each call (stateless protocol).
        Returns None on timeout or any other error so callers can handle
        missing data gracefully.

        Args:
            command: Plain-text KEBA command string, e.g. "report 2" or "curr 11000".
            timeout: Socket receive timeout in seconds.
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)
        try:
            sock.sendto(command.encode(), (self.host, self.port))
            data, _ = sock.recvfrom(4096)
            return json.loads(data.decode())
        except socket.timeout:
            _LOGGER.warning("Timeout sending '%s' to %s:%s", command, self.host, self.port)
            return None
        except Exception as err:
            _LOGGER.error("Error sending '%s' to %s:%s: %s", command, self.host, self.port, err)
            return None
        finally:
            sock.close()

    def send_command(self, command: str) -> bool:
        """Send a fire-and-forget control command to the charger.

        Used by switch/number/select entities to change charger state.
        The charger acknowledges most commands with a small JSON response;
        we only check whether a response arrived, not its content.

        Returns True if the charger responded, False on timeout/error.
        """
        result = self._send(command)
        return result is not None

    # ------------------------------------------------------------------
    # Coordinator update cycle
    # ------------------------------------------------------------------

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch all reports and return a flat dict of normalised values.

        Called automatically by the coordinator on every poll interval.
        All blocking socket I/O is offloaded to the executor thread pool
        via async_add_executor_job so the HA event loop is never blocked.

        Raises UpdateFailed if the charger is unreachable or returns
        incomplete data (report 2 and 3 are mandatory).
        """
        try:
            r1, r2, r3, r100 = await self.hass.async_add_executor_job(self._fetch_all)
        except Exception as err:
            raise UpdateFailed(f"Error communicating with KEBA charger: {err}") from err

        # report 2 (state/limits) and report 3 (measurements) are essential
        if not r2 or not r3:
            raise UpdateFailed("Incomplete data from KEBA charger (report 2 or 3 missing)")

        return {
            # ── report 1: device identity ─────────────────────────────
            "product":    r1.get("Product", "") if r1 else "",
            "serial":     r1.get("Serial", "") if r1 else "",
            "firmware":   r1.get("Firmware", "") if r1 else "",
            "com_module": r1.get("COM-module", 0) if r1 else 0,  # 1 = COM module present
            "backend":    r1.get("Backend", 0) if r1 else 0,     # 1 = connected to OCPP backend

            # ── report 2: charging system state ──────────────────────
            "state":         r2.get("State", 0),       # 0-5, see KEBA_STATE_CODES
            "error1":        r2.get("Error1", 0),      # error code (0 = no error)
            "error2":        r2.get("Error2", 0),      # secondary error code
            "plug":          r2.get("Plug", 0),        # 0 = unplugged, non-zero = plugged
            "auth_on":       bool(r2.get("AuthON", 0)),    # RFID authorisation active
            "auth_req":      bool(r2.get("Authreq", 0)),   # RFID authorisation required
            "enable_sys":    bool(r2.get("Enable sys", 0)),  # charging allowed by system
            "enable_user":   bool(r2.get("Enable user", 0)),  # charging allowed by user
            "max_curr_ma":   r2.get("Max curr", 0),    # actual effective limit (mA)
            "max_curr_pct":  r2.get("Max curr %", 1000),  # effective limit as percentage (0-1000 → 0-100 %)
            "curr_hw_ma":    r2.get("Curr HW", 0),     # hardware maximum (mA), typically 16000
            "curr_user_ma":  r2.get("Curr user", 0),   # user-set limit (mA)
            "curr_fs_ma":    r2.get("Curr FS", 0),     # failsafe current if backend lost (mA)
            "tmo_fs":        r2.get("Tmo FS", 0),      # failsafe timeout (s)
            "curr_timer_ma": r2.get("Curr timer", 0),  # current set via currtime command (mA)
            "tmo_ct":        r2.get("Tmo CT", 0),      # countdown for currtime command (s)
            "setenergy":     r2.get("Setenergy", 0),   # energy target for current session (0.1 Wh)
            "phase_switch":  r2.get("X2 phaseSwitch", 0),  # active phase count (1/2/3)
            "phase_default": r2.get("X2 default", 0),      # default phase count after reboot

            # ── report 3: live measurements ───────────────────────────
            # Voltages in V, currents in mA, power in mW, energy in 0.1 Wh
            "voltage_l1":          r3.get("U1", 0),
            "voltage_l2":          r3.get("U2", 0),
            "voltage_l3":          r3.get("U3", 0),
            "current_l1_ma":       r3.get("I1", 0),
            "current_l2_ma":       r3.get("I2", 0),
            "current_l3_ma":       r3.get("I3", 0),
            "power_mw":            r3.get("P", 0),   # total active power
            "power_factor":        r3.get("PF", 0),  # ×0.1 → % (e.g. 1000 = 100 %)
            "energy_session_01wh": r3.get("E pres", 0),   # energy in current session
            "energy_total_01wh":   r3.get("E total", 0),  # total lifetime energy

            # ── report 100: OCPP session data ─────────────────────────
            "session_id":       r100.get("Session ID", 0) if r100 else 0,
            "session_started":  r100.get("started", "") if r100 else "",   # ISO timestamp
            "session_ended":    r100.get("ended", "") if r100 else "",
            "session_duration_s": r100.get("started[s]", 0) if r100 else 0,  # seconds since start
            "rfid_tag":         r100.get("RFID tag", "") if r100 else "",
            "rfid_class":       r100.get("RFID class", "") if r100 else "",
            "session_reason":   r100.get("reason", 0) if r100 else 0,  # stop reason code
        }

    def _fetch_all(self) -> tuple:
        """Blocking helper: send all four report requests sequentially.

        Must run in an executor thread (called via async_add_executor_job).
        Sends each report independently so partial results are still usable
        if one report times out.
        """
        r1   = self._send("report 1")
        r2   = self._send("report 2")
        r3   = self._send("report 3")
        r100 = self._send("report 100")
        return r1, r2, r3, r100
