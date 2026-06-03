# SolarEdge One EV Charger – Home Assistant Custom Integration

A Home Assistant custom integration for the **SolarEdge ONE EV Charger** (hardware: KEBA P30).
Communicates directly via the **KEBA UDP protocol** on the local network — no cloud, no SolarEdge account required.

---

## Features

| Platform | Entity | Default |
|----------|--------|---------|
| Binary Sensor | Vehicle Connected (`binary_sensor.*_vehicle_connected`) | ✅ enabled |
| Binary Sensor | Charging (`binary_sensor.*_charging`) | ✅ enabled |
| Sensor | Charging State | ✅ enabled |
| Sensor | Charging Power (W) | ✅ enabled |
| Sensor | Session Energy (Wh) | ✅ enabled |
| Sensor | Total Energy (kWh) | ✅ enabled |
| Sensor | Current L1 / L2 / L3 (A) | ✅ enabled |
| Sensor | Current Limit User (A) | ✅ enabled |
| Sensor | Voltage L1 / L2 / L3 (V) | ☑ disabled |
| Sensor | Power Factor (%) | ☑ disabled |
| Sensor | Current Limit Hardware / Failsafe (A) | ☑ disabled |
| Sensor | Plug Status | ☑ disabled |
| Sensor | Session Duration (s) | ☑ disabled |
| Sensor | RFID Tag | ☑ disabled |
| Sensor | Firmware | ☑ disabled |
| Sensor | Error Code 1 / 2 | ☑ disabled |
| Switch | Charging Enabled | ✅ enabled |
| Number | Charging Current (6–16 A slider) | ✅ enabled |
| Select | Phase Mode (1-phase / 3-phase) | ✅ enabled |

Disabled entities can be enabled individually under
**Settings → Devices & Services → SolarEdge One EV Charger → device → (entity list)**.

---

## Requirements

- Home Assistant 2024.1 or newer
- SolarEdge ONE EV Charger (KEBA P30 OEM) reachable on the local network
- UDP port **7090** accessible from the Home Assistant host

> **No additional Python packages required.** The integration uses only the Python standard library (`socket`, `json`).

---

## Installation

### Manual

1. Download or clone this repository.
2. Copy the `keba_one_ev` folder into your HA config directory:
   ```
   <config>/custom_components/keba_one_ev/
   ```
3. Restart Home Assistant.
4. Go to **Settings → Devices & Services → Add Integration** and search for **SolarEdge One EV Charger**.

### HACS (manual repository)

1. In HACS, go to **Integrations → ⋮ → Custom repositories**.
2. Add this repository URL with category **Integration**.
3. Install **SolarEdge One EV Charger** and restart Home Assistant.

---

## Configuration

After installation, add the integration via the UI:

| Field | Default | Description |
|-------|---------|-------------|
| IP-Adresse | `xxx.xxx.xxx.xxx` | IP address of the charger |
| UDP Port | `7090` | KEBA UDP port (do not change unless your network requires it) |
| Abfrageintervall | `10` | Polling interval in seconds |

During setup a live connection test is performed — the integration sends `report 1` to the charger and verifies the response before saving.

---

## Protocol Background

The SolarEdge ONE EV Charger is a rebranded **KEBA P30**.
It uses the proprietary **KEBA UDP protocol**:

```
Transport:  UDP unicast
Port:       7090 (charger listens)
Request:    plain-text ASCII command  (e.g.  report 2)
Response:   JSON object
```

### Read commands

| Command | Content |
|---------|---------|
| `report 1` | Product name, serial number, firmware version |
| `report 2` | Charging state, enable flags, current limits, phase mode |
| `report 3` | Live measurements: voltage, current, power, energy |
| `report 100` | OCPP session data: RFID tag, session timestamps |

### Write commands

| Command | Effect |
|---------|--------|
| `ena 1` / `ena 0` | Enable / disable charging |
| `curr <mA>` | Set charging current limit (min 6000, max 16000) |
| `currtime <mA> <s>` | Set current limit with automatic timeout |
| `xswitchphase 1` / `xswitchphase 3` | Switch to 1-phase / 3-phase mode |

### Unit conventions

| Field | Raw unit | Converted to |
|-------|----------|-------------|
| Currents | milliamperes (mA) | A (÷ 1000) |
| Power | milliwatts (mW) | W (÷ 1000) |
| Energy | 0.1 Wh | Wh (× 0.1) or kWh (× 0.0001) |
| Power factor | 0–1000 | % (÷ 10) |
| Voltage | V | V (no conversion) |

---

## Tested Hardware

| Device | Firmware | Status |
|--------|----------|--------|
| SolarEdge ONE EV Charger (KEBA P30 OEM), S/N 99206288 | 04.00.44 | ✅ Working |

Other KEBA P30 variants that speak the same UDP protocol should work too, but have not been tested.

---

## keba-charger-card

The [keba-charger-card](https://github.com/pail23/keba-charger-card) Lovelace card works with this integration.
Use the `vehicle_connected` binary sensor as the main entity and map the stats manually:

```yaml
type: custom:keba-charger-card
entity: binary_sensor.<device>_vehicle_connected
stats:
  - entity_id: sensor.<device>_power
    unit: W
    subtitle: Charging Power
  - entity_id: sensor.<device>_energy_session
    unit: Wh
    subtitle: Session Energy
  - entity_id: sensor.<device>_current_l1
    unit: A
    subtitle: Current L1
```

Replace `<device>` with your actual device name (visible in **Settings → Devices & Services**).

---

## Related Integrations

This integration covers the EV charger only.
For the SolarEdge inverter (Modbus TCP), use the excellent
[solaredge-modbus-multi](https://github.com/WillCodeForCats/solaredge-modbus-multi) HACS integration.

---

## License

MIT
