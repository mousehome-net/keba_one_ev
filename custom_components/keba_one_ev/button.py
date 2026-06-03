"""Button platform for the SE One EV Charger integration.

Provides a button entity to unlock the charging cable.

KEBA command used:
  unlock  →  release the cable lock so the cable can be unplugged

Useful when the vehicle or charging session holds the cable locked
and the user wants to remove it without ending the session via the car.
"""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
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
    """Create the unlock button entity for this config entry."""
    coordinator: KebaCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([KebaUnlockButton(coordinator, entry)])


class KebaUnlockButton(CoordinatorEntity[KebaCoordinator], ButtonEntity):
    """Button that unlocks the EV charging cable."""

    _attr_has_entity_name = True
    _attr_translation_key = "unlock_cable"
    _attr_icon = "mdi:lock-open-variant"

    def __init__(self, coordinator: KebaCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_unlock"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
        }

    async def async_press(self) -> None:
        """Send the unlock command to the charger."""
        await self.hass.async_add_executor_job(
            self.coordinator.send_command, "unlock"
        )
