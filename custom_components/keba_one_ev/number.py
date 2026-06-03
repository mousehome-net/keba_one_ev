"""Number platform for the SE One EV Charger integration.

Provides two slider entities:
  - charging_current:      charging current 6–16 A  (command: curr <mA>)
  - charging_energy_target: session energy limit 0–100 kWh (command: setenergy <0.1Wh>)
    Setting 0 disables the energy limit (charge without limit).
"""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfElectricCurrent, UnitOfEnergy
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
    async_add_entities([
        KebaCurrentNumber(coordinator, entry),
        KebaSetEnergyNumber(coordinator, entry),
    ])


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


class KebaSetEnergyNumber(CoordinatorEntity[KebaCoordinator], NumberEntity):
    """Number to set a per-session energy limit (0 = unlimited, 1–100 kWh).

    KEBA command: setenergy <value_in_0.1Wh>
    Example: 10 kWh → setenergy 100000
    Setting 0 disables the limit.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "charging_energy_target"
    _attr_icon = "mdi:lightning-bolt"
    _attr_native_min_value = 0.0    # 0 = no limit
    _attr_native_max_value = 100.0  # 100 kWh
    _attr_native_step = 0.1
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator: KebaCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_set_energy"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
        }

    @property
    def native_value(self) -> float | None:
        """Return the current energy target in kWh (0 = disabled)."""
        data = self.coordinator.data
        if data is None:
            return None
        # setenergy is stored in 0.1 Wh units → convert to kWh
        return round(data.get("setenergy", 0) * 0.1 / 1000, 2)

    async def async_set_native_value(self, value: float) -> None:
        """Send the new energy target to the charger (setenergy <0.1Wh>)."""
        # kWh → 0.1 Wh: multiply by 10000
        energy_01wh = int(value * 10000)
        await self.hass.async_add_executor_job(
            self.coordinator.send_command, f"setenergy {energy_01wh}"
        )
        await self.coordinator.async_request_refresh()
