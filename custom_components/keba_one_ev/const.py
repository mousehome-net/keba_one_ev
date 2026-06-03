"""Constants for the SE One EV Charger integration.

This integration communicates with a SolarEdge ONE EV Charger (hardware: KEBA P30)
via the KEBA UDP protocol on port 7090.

Protocol notes:
  - Commands are sent as plain-text UDP datagrams (e.g. "report 2")
  - Responses are JSON objects
  - Currents are expressed in milliamperes (mA) in the protocol
  - Energy values use 0.1 Wh as the base unit
  - Power values are in milliwatts (mW)
"""

DOMAIN = "keba_one_ev"

# Default connection parameters – adjust to your network if needed
DEFAULT_HOST = "192.168.1.76"
DEFAULT_PORT = 7090          # KEBA UDP port, fixed by the hardware
DEFAULT_SCAN_INTERVAL = 10   # seconds between polls

# Config entry keys (stored in entry.data)
CONF_HOST = "host"
CONF_PORT = "port"
CONF_SCAN_INTERVAL = "scan_interval"

# Charger state codes returned by "report 2" → "State"
# Values are translation keys resolved via strings.json / translations/*.json
KEBA_STATE_CODES = {
    0: "startup",
    1: "no_vehicle",
    2: "connected",
    3: "charging",
    4: "error",
    5: "interrupted",
}

# Phase mode labels returned by "report 2" → "X2 phaseSwitch"
# Values are translation keys; 2-phase (uncommon hardware) treated as 1-phase
KEBA_PHASE_MODES = {
    1: "1_phase",
    2: "1_phase",
    3: "3_phase",
}

# Hardware limits for charging current (in mA)
# KEBA requires a minimum of 6 A; 0 A means stop charging via curr command
KEBA_MIN_CURRENT_MA = 6000
KEBA_MAX_CURRENT_MA = 16000
