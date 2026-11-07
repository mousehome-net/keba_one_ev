"""Number platform for the SE One EV Charger integration.

Provides one slider entity:
  - charging_current: charging current 6–16 A  (command: curr <mA>)

An energy-target slider (setenergy) was removed: on the firmware tested so far
it does not stop a session, it only interrupts charging for a few seconds
(issue #12).
"""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfElectricCurrent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, KEBA_MAX_CURRENT_MA, KEBA_MIN_CURRENT_MA
from .coordinator import KebaCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create number entities for this config entry."""
    coordinator: KebaCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([KebaCurrentNumber(coordinator, entry)])


class KebaCurrentNumber(CoordinatorEntity[KebaCoordinator], NumberEntity):
    """Slider to set the EV charging current (6–16 A)."""

    _attr_has_entity_name = True
    _attr_translation_key = "charging_current"
    _attr_icon = "mdi:current-ac"
    _attr_native_min_value = KEBA_MIN_CURRENT_MA / 1000   # 6 A
    _attr_native_max_value = KEBA_MAX_CURRENT_MA / 1000   # 16 A
    _attr_native_step = 1.0                               # 1 A steps
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator: KebaCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_charging_current"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
        }

    @property
    def native_value(self) -> float | None:
        """Return the current user-set charging limit in amperes."""
        data = self.coordinator.data
        if data is None:
            return None
        return round(data.get("curr_user_ma", KEBA_MAX_CURRENT_MA) / 1000, 1)

    async def async_set_native_value(self, value: float) -> None:
        """Send the new current limit to the charger (curr <mA>)."""
        current_ma = int(value * 1000)
        current_ma = max(KEBA_MIN_CURRENT_MA, min(KEBA_MAX_CURRENT_MA, current_ma))
        await self.hass.async_add_executor_job(
            self.coordinator.send_command, f"curr {current_ma}"
        )
        await self.coordinator.async_request_refresh()
