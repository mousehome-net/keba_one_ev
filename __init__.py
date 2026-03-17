"""SE One EV Charger – Home Assistant custom integration.

Integrates the SolarEdge ONE EV Charger (hardware: KEBA P30) into Home Assistant
via the KEBA UDP protocol. Provides sensors, a charging switch, a current slider,
and a phase-mode selector.

Setup flow:
  1. User adds the integration via the UI (config_flow.py).
  2. async_setup_entry() creates a KebaCoordinator and performs the first data fetch.
  3. The coordinator is stored in hass.data[DOMAIN][entry.entry_id] so all entity
     platforms can access it without creating additional connections.
  4. All four platforms (sensor, switch, number, select) are forwarded to their
     respective modules.
"""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL, DEFAULT_PORT, DEFAULT_SCAN_INTERVAL
from .coordinator import KebaCoordinator

_LOGGER = logging.getLogger(__name__)

# All platforms provided by this integration
PLATFORMS = ["sensor", "switch", "number", "select", "button"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SE One EV Charger from a config entry.

    Called by HA after the user completes the config flow or on HA restart
    when an existing entry is present.
    """
    host = entry.data[CONF_HOST]
    port = entry.data.get(CONF_PORT, DEFAULT_PORT)
    scan_interval = entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

    # Create the coordinator that handles all UDP communication with the charger
    coordinator = KebaCoordinator(hass, host, port, scan_interval)

    # Perform the initial data fetch; raises ConfigEntryNotReady on failure
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator so entity platforms can retrieve it by entry_id
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    # Spin up all platforms (sensor.py, switch.py, number.py, select.py)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry and clean up all associated entities."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
