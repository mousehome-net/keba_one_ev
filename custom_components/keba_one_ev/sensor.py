"""Sensor platform for the SE One EV Charger integration.

Creates 21 sensor entities from the data provided by KebaCoordinator.
Sensors are split into two groups:

  Enabled by default (visible without extra steps):
    - charging_state    charging state (translated via strings.json)
    - power             active charging power in W
    - energy_session    energy charged in the current session (Wh)
    - energy_total      total lifetime energy (kWh)
    - current_l1/l2/l3  per-phase current in A
    - current_limit_user user-set current limit in A

  Disabled by default (can be enabled in HA entity registry):
    - voltage_l1/l2/l3          per-phase voltage in V
    - power_factor               power factor in %
    - current_limit_hw           fixed hardware maximum in A
    - current_limit_failsafe     current when backend connection is lost
    - current_limit_pct          user limit as percentage
    - plug                       plug connected / disconnected (translated)
    - session_duration           session duration in seconds
    - rfid_tag                   RFID card ID used to authorise the session
    - firmware                   charger firmware version
    - error1 / error2            error codes (0 = no error)

All sensors share the same KebaCoordinator instance, so no additional
UDP connections are opened.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, KEBA_STATE_CODES
from .coordinator import KebaCoordinator


@dataclass(frozen=True)
class KebaSensorDescription(SensorEntityDescription):
    """Extends SensorEntityDescription with KEBA-specific fields.

    Attributes:
        data_key:       Key in coordinator.data (informational, not used directly).
        value_fn:       Callable that receives the full coordinator data dict and
                        returns the sensor value.  Keeps all conversion logic here
                        rather than scattered across entity classes.
        enabled_default: Whether the entity is enabled in the registry by default.
    """

    data_key: str = ""
    value_fn: Any = None
    enabled_default: bool = True


# ---------------------------------------------------------------------------
# Sensor definitions
# ---------------------------------------------------------------------------
# Each entry produces exactly one entity.  Conversion from raw KEBA units to
# HA-native units happens in value_fn:
#   currents  : raw mA  → A   (÷ 1000)
#   power     : raw mW  → W   (÷ 1000)
#   energy    : raw 0.1Wh → Wh (× 0.1) or kWh (× 0.0001)
#   PF        : raw 0–1000 → % (÷ 10)
#
# Entity names come from translations (strings.json / translations/*.json)
# via translation_key — no hardcoded name= strings here.
# ---------------------------------------------------------------------------
SENSORS: tuple[KebaSensorDescription, ...] = (

    # ── Enabled by default ────────────────────────────────────────────────

    KebaSensorDescription(
        key="charging_state",
        translation_key="charging_state",
        device_class=SensorDeviceClass.ENUM,
        icon="mdi:ev-station",
        options=list(KEBA_STATE_CODES.values()),
        data_key="state",
        value_fn=lambda d: KEBA_STATE_CODES.get(d.get("state", 0)),
        enabled_default=True,
    ),
    KebaSensorDescription(
        key="power",
        translation_key="power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        data_key="power_mw",
        value_fn=lambda d: round(d.get("power_mw", 0) / 1000, 1),  # mW → W
        enabled_default=True,
    ),
    KebaSensorDescription(
        key="energy_session",
        translation_key="energy_session",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        data_key="energy_session_01wh",
        value_fn=lambda d: round(d.get("energy_session_01wh", 0) * 0.1, 1),  # 0.1 Wh → Wh
        enabled_default=True,
    ),
    KebaSensorDescription(
        key="energy_total",
        translation_key="energy_total",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        data_key="energy_total_01wh",
        value_fn=lambda d: round(d.get("energy_total_01wh", 0) * 0.1 / 1000, 2),  # 0.1 Wh → kWh
        enabled_default=True,
    ),
    KebaSensorDescription(
        key="current_l1",
        translation_key="current_l1",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        data_key="current_l1_ma",
        value_fn=lambda d: round(d.get("current_l1_ma", 0) / 1000, 2),  # mA → A
        enabled_default=True,
    ),
    KebaSensorDescription(
        key="current_l2",
        translation_key="current_l2",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        data_key="current_l2_ma",
        value_fn=lambda d: round(d.get("current_l2_ma", 0) / 1000, 2),
        enabled_default=True,
    ),
    KebaSensorDescription(
        key="current_l3",
        translation_key="current_l3",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        data_key="current_l3_ma",
        value_fn=lambda d: round(d.get("current_l3_ma", 0) / 1000, 2),
        enabled_default=True,
    ),
    KebaSensorDescription(
        key="current_limit_user",
        translation_key="current_limit_user",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        data_key="curr_user_ma",
        value_fn=lambda d: round(d.get("curr_user_ma", 0) / 1000, 1),
        enabled_default=True,
    ),

    # ── Disabled by default ───────────────────────────────────────────────

    KebaSensorDescription(
        key="voltage_l1",
        translation_key="voltage_l1",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        data_key="voltage_l1",
        value_fn=lambda d: d.get("voltage_l1", 0),  # already in V
        enabled_default=False,
    ),
    KebaSensorDescription(
        key="voltage_l2",
        translation_key="voltage_l2",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        data_key="voltage_l2",
        value_fn=lambda d: d.get("voltage_l2", 0),
        enabled_default=False,
    ),
    KebaSensorDescription(
        key="voltage_l3",
        translation_key="voltage_l3",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        data_key="voltage_l3",
        value_fn=lambda d: d.get("voltage_l3", 0),
        enabled_default=False,
    ),
    KebaSensorDescription(
        key="power_factor",
        translation_key="power_factor",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:sine-wave",
        data_key="power_factor",
        value_fn=lambda d: round(d.get("power_factor", 0) / 10, 1),  # 0-1000 → 0-100 %
        enabled_default=False,
    ),
    KebaSensorDescription(
        key="current_limit_pct",
        translation_key="current_limit_pct",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:percent",
        data_key="max_curr_pct",
        value_fn=lambda d: round(d.get("max_curr_pct", 1000) / 10, 1),  # 0-1000 → 0-100 %
        enabled_default=False,
    ),
    KebaSensorDescription(
        key="current_limit_hw",
        translation_key="current_limit_hw",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        data_key="curr_hw_ma",
        value_fn=lambda d: round(d.get("curr_hw_ma", 0) / 1000, 1),
        enabled_default=False,
    ),
    KebaSensorDescription(
        key="current_limit_failsafe",
        translation_key="current_limit_failsafe",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        data_key="curr_fs_ma",
        # Applied when the OCPP backend connection is lost
        value_fn=lambda d: round(d.get("curr_fs_ma", 0) / 1000, 1),
        enabled_default=False,
    ),
    KebaSensorDescription(
        key="plug",
        translation_key="plug",
        device_class=SensorDeviceClass.ENUM,
        icon="mdi:power-plug",
        options=["connected", "disconnected"],
        data_key="plug",
        value_fn=lambda d: "connected" if d.get("plug") else "disconnected",
        enabled_default=False,
    ),
    KebaSensorDescription(
        key="session_duration",
        translation_key="session_duration",
        icon="mdi:timer",
        native_unit_of_measurement="s",
        data_key="session_duration_s",
        value_fn=lambda d: d.get("session_duration_s", 0),
        enabled_default=False,
    ),
    KebaSensorDescription(
        key="rfid_tag",
        translation_key="rfid_tag",
        icon="mdi:card-account-details",
        data_key="rfid_tag",
        value_fn=lambda d: d.get("rfid_tag", ""),
        enabled_default=False,
    ),
    KebaSensorDescription(
        key="firmware",
        translation_key="firmware",
        icon="mdi:chip",
        data_key="firmware",
        value_fn=lambda d: d.get("firmware", ""),
        enabled_default=False,
    ),
    KebaSensorDescription(
        key="error1",
        translation_key="error1",
        icon="mdi:alert-circle",
        data_key="error1",
        value_fn=lambda d: d.get("error1", 0),  # 0 = no error
        enabled_default=False,
    ),
    KebaSensorDescription(
        key="error2",
        translation_key="error2",
        icon="mdi:alert-circle",
        data_key="error2",
        value_fn=lambda d: d.get("error2", 0),
        enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create all sensor entities for this config entry."""
    coordinator: KebaCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(KebaSensor(coordinator, entry, desc) for desc in SENSORS)


class KebaSensor(CoordinatorEntity[KebaCoordinator], SensorEntity):
    """A single sensor entity backed by the KEBA coordinator."""

    entity_description: KebaSensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: KebaCoordinator,
        entry: ConfigEntry,
        description: KebaSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_entity_registry_enabled_default = description.enabled_default
        # Device info ties all entities from this entry to one device card in HA
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title,
            "manufacturer": "KEBA / SolarEdge",
            "model": coordinator.data.get("product", "ONE_EV"),
            "sw_version": coordinator.data.get("firmware", ""),
            "serial_number": coordinator.data.get("serial", ""),
        }

    @property
    def native_value(self):
        """Compute the sensor value from the latest coordinator data."""
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)
