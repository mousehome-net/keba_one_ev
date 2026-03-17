"""Select platform for the SE One EV Charger integration.

Provides a dropdown to switch between 1-phase and 3-phase charging mode.

KEBA command used:
  xswitchphase 1  →  switch to single-phase charging
  xswitchphase 3  →  switch to three-phase charging

Background: The SolarEdge ONE EV Charger supports dynamic phase switching
(KEBA X2 feature).  Charging at 1-phase allows finer power steps at low
surplus PV power (230 V × 6–16 A = 1.4–3.7 kW), while 3-phase charging
uses higher power (400 V × 6–16 A = 4.1–11 kW).

The current phase mode is read from "report 2" → "X2 phaseSwitch":
  1 = 1-phase active
  2 = 2-phase active (hardware-specific, not selectable here)
  3 = 3-phase active
"""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import KebaCoordinator

# Options shown in the HA UI dropdown
PHASE_OPTIONS = ["1-phasig", "3-phasig"]

# Map UI label → KEBA command
PHASE_TO_CMD = {
    "1-phasig": "xswitchphase 1",
    "3-phasig": "xswitchphase 3",
}

# Map raw integer from report 2 → UI label
# Value 2 (2-phase) is reported by some hardware variants; treat as 1-phase
PHASE_FROM_INT = {1: "1-phasig", 2: "1-phasig", 3: "3-phasig"}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the phase-mode selector entity for this config entry."""
    coordinator: KebaCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([KebaPhaseSelect(coordinator, entry)])


class KebaPhaseSelect(CoordinatorEntity[KebaCoordinator], SelectEntity):
    """Dropdown to choose between 1-phase and 3-phase charging."""

    _attr_has_entity_name = True
    _attr_name = "Phasenmodus"
    _attr_icon = "mdi:lightning-bolt-circle"
    _attr_options = PHASE_OPTIONS

    def __init__(self, coordinator: KebaCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_phase_mode"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
        }

    @property
    def current_option(self) -> str | None:
        """Return the currently active phase mode as a UI label."""
        data = self.coordinator.data
        if data is None:
            return None
        # Default to 3-phase if the value is missing or unexpected
        return PHASE_FROM_INT.get(data.get("phase_switch", 3), "3-phasig")

    async def async_select_option(self, option: str) -> None:
        """Send the xswitchphase command and refresh coordinator data."""
        cmd = PHASE_TO_CMD.get(option)
        if cmd:
            await self.hass.async_add_executor_job(self.coordinator.send_command, cmd)
            await self.coordinator.async_request_refresh()
