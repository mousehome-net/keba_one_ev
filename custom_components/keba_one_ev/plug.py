"""Interpretation of the KEBA "Plug" field from report 2.

Plug is a bitmask, not a boolean (see issue #4):

  bit 0 (1) -- cable plugged into the charging station
  bit 1 (2) -- cable locked at the station
  bit 2 (4) -- cable plugged into the vehicle

Known combinations: 0, 1, 3, 5, 7. On socket-model chargers it's normal
to leave the cable in the station with no car attached (Plug=1), so a
vehicle is only actually connected when bit 2 is set.
"""
from __future__ import annotations

_VEHICLE_BIT = 1 << 2


def is_vehicle_connected(plug: int | None) -> bool:
    """True only when the connector is plugged into the vehicle."""
    return bool((plug or 0) & _VEHICLE_BIT)
