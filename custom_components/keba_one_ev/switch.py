"""Switch platform for the SE One EV Charger integration.

Provides a single switch entity that enables or disables charging.

KEBA commands used:
  ena 1  →  allow charging (sets the user-enable flag)
  ena 0  →  prevent charging (clears the user-enable flag)

Note: The charger also has a separate system-enable flag ("Enable sys") that
is controlled by the OCPP backend.  The switch reflects the combined state
(both system AND user enable must be active for charging to proceed), but
only the user flag is toggled – the system flag is managed by the backend.
"""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import KebaCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the charging switch entity for this config entry."""
    coordinator: KebaCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([KebaChargingSwitch(coordinator, entry)])


class KebaChargingSwitch(CoordinatorEntity[KebaCoordinator], SwitchEntity):
    """Switch that enables or disables EV charging."""

    _attr_has_entity_name = True
    _attr_translation_key = "charging_enabled"
    _attr_icon = "mdi:ev-plug-type2"

    def __init__(self, coordinator: KebaCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_charging_enabled"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
        }

    @property
    def is_on(self) -> bool:
        """Return True only when both system- and user-enable flags are set."""
        data = self.coordinator.data
        if data is None:
            return False
        return bool(data.get("enable_sys") and data.get("enable_user"))

    async def async_turn_on(self, **kwargs) -> None:
        """Enable charging by setting the user-enable flag (ena 1)."""
        await self.hass.async_add_executor_job(self.coordinator.send_command, "ena 1")
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Disable charging by clearing the user-enable flag (ena 0)."""
        await self.hass.async_add_executor_job(self.coordinator.send_command, "ena 0")
        await self.coordinator.async_request_refresh()
