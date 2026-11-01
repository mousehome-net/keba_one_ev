"""Binary sensor platform for the SE One EV Charger integration.

Provides binary sensors derived from coordinator data:

  vehicle_connected   True only when the cable is plugged into the vehicle,
                      not merely into the station (see plug.py). Enabled by
                      default — useful for automations and cards.

  charging            True when the charger is actively delivering power
                      (KEBA state == 3).  Enabled by default.

  backend_connected   True when the charger has an active OCPP/backend
                      connection (KEBA report 1 "Backend"). On SolarEdge
                      ONE units this is typically the SolarEdge app/cloud,
                      which can push its own current limit independently
                      of this integration. Disabled by default.

  com_module_present  True when the charger's communication module is
                      installed (KEBA report 1 "COM-module"). Disabled by
                      default.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import KebaCoordinator
from .plug import is_vehicle_connected


@dataclass(frozen=True)
class KebaBinarySensorDescription(BinarySensorEntityDescription):
    """Extends BinarySensorEntityDescription with a value callable."""

    value_fn: Any = None
    enabled_default: bool = True


BINARY_SENSORS: tuple[KebaBinarySensorDescription, ...] = (
    KebaBinarySensorDescription(
        key="vehicle_connected",
        translation_key="vehicle_connected",
        device_class=BinarySensorDeviceClass.PLUG,
        value_fn=lambda d: is_vehicle_connected(d.get("plug")),
    ),
    KebaBinarySensorDescription(
        key="charging",
        translation_key="charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        value_fn=lambda d: d.get("state") == 3,
    ),
    KebaBinarySensorDescription(
        key="backend_connected",
        translation_key="backend_connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda d: bool(d.get("backend")),
        enabled_default=False,
    ),
    KebaBinarySensorDescription(
        key="com_module_present",
        translation_key="com_module_present",
        value_fn=lambda d: bool(d.get("com_module")),
        enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create binary sensor entities for this config entry."""
    coordinator: KebaCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        KebaBinarySensor(coordinator, entry, desc) for desc in BINARY_SENSORS
    )


class KebaBinarySensor(CoordinatorEntity[KebaCoordinator], BinarySensorEntity):
    """A binary sensor backed by the KEBA coordinator."""

    entity_description: KebaBinarySensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: KebaCoordinator,
        entry: ConfigEntry,
        description: KebaBinarySensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_entity_registry_enabled_default = description.enabled_default
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title,
            "manufacturer": "KEBA / SolarEdge",
            "model": coordinator.data.get("product", "ONE_EV"),
            "sw_version": coordinator.data.get("firmware", ""),
            "serial_number": coordinator.data.get("serial", ""),
        }

    @property
    def is_on(self) -> bool | None:
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)
