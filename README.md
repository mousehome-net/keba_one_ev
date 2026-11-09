# SolarEdge One EV Charger – Home Assistant Custom Integration

A Home Assistant custom integration for the **SolarEdge ONE EV Charger** (hardware: KEBA P30).
Communicates directly via the **KEBA UDP protocol** on the local network — no cloud, no SolarEdge account required.

---

## Features

| Platform | Entity | Default |
|----------|--------|---------|
| Binary Sensor | Plug — vehicle physically connected (`binary_sensor.*_vehicle_connected`) | ✅ enabled |
| Binary Sensor | Charging — actively delivering power (`binary_sensor.*_charging`) | ✅ enabled |
| Binary Sensor | Backend Connected — OCPP/backend link active (e.g. SolarEdge app/cloud) | ☑ disabled |
| Binary Sensor | COM Module Present | ☑ disabled |
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
| Number | Charging Current (6–16 A slider) | ✅ enabled |
| Select | Phase Mode (1-phase / 3-phase) (⚠️ unverified, see below; shows *unknown* on units without a phase switch) | ✅ enabled |
| Button | Unlock Cable | ✅ enabled |

Entities keep their last value over one or two failed polls in a row (for example on a
slow WiFi link) before they become unavailable.

Disabled entities can be enabled individually under
**Settings → Devices & Services → SolarEdge One EV Charger → device → (entity list)**.

### What you can automate

**Reading always works** and is safe to build automations on: vehicle connected,
charging, charging state, power, current and voltage per phase, session energy
and duration, total energy, error codes and whether a back office is attached.
Use these for notifications, statistics or cost tracking.

**Controlling the charger is more limited.** Verified on a SolarEdge ONE
(FW 04.00.70) with and without a vehicle in an active session, and for the
current also by a user on FW 04.00.42:

| Action | Verified | Notes |
|--------|----------|-------|
| Set charging current (6–16 A) | ✅ value stays, and in an active session the real current follows it | This is the control that works reliably, for example for PV surplus charging. |
| Pause charging with `curr 0` | ❌ does not pause an active session | Accepted without a car (`Curr user` becomes 0). In an active session the current dropped to ~0 A for about 3–10 s and then returned to full without any command, `Curr user` stayed unchanged (FW 04.00.70 and, in #12, FW 04.00.42). |
| Start / stop a session | ❌ not possible through this interface | `ena`, `curr 0`, `currtime 0 1` and the energy target (`setenergy`) were all tested and do not stop a session. The energy target only interrupts charging for 4–7 s (#12, FW 04.00.42). Stop it from the car or its app. |
| Phase mode (`xswitchphase`) | ❌ no effect | Empty reply; in an active session on FW 04.00.70 the phases and `X2 phaseSwitch` stayed unchanged for over a minute. The phase switch documented by KEBA (`x2src 4`, then `x2 0`) also had no effect; it drives an *external* switch via contact X2. `xswitchphase` is not in the KEBA guides. |
| Unlock cable | ⚠️ no effect during a session | Replies `TCH-OK`, but with a session running the cable stayed locked (`Plug` 7) and charging continued. Not tested while idle. |

Entities marked ⚠️ may change or be removed once their behaviour is confirmed.

---

## Requirements

- Home Assistant 2024.1 or newer
- SolarEdge ONE EV Charger (KEBA P30 OEM) reachable on the local network
- UDP port **7090** accessible from the Home Assistant host

> **No additional Python packages required.** The integration uses only the Python standard library (`socket`, `json`).

---

## Installation

### Marketplace (recommended, Home Assistant 2026.11 or newer)

This integration is listed in the default repository that the Home Assistant
Marketplace uses.

1. Go to **Settings → Marketplace** and search for **SolarEdge One EV Charger**.
2. Download it and restart Home Assistant.
3. Go to **Settings → Devices & Services → Add Integration** and search for **SolarEdge One EV Charger**.

### HACS (Home Assistant 2026.10 or older)

On older Home Assistant versions the same listing is available through HACS.

1. In HACS, go to **Integrations** and search for **SolarEdge One EV Charger**.
2. Click **Download** and restart Home Assistant.
3. Go to **Settings → Devices & Services → Add Integration** and search for **SolarEdge One EV Charger**.

Installations made with HACS keep receiving updates after upgrading to 2026.11,
the Marketplace takes them over.

### Manual

1. Download or clone this repository.
2. Copy the `keba_one_ev` folder into your HA config directory:
   ```
   <config>/custom_components/keba_one_ev/
   ```
3. Restart Home Assistant.
4. Go to **Settings → Devices & Services → Add Integration** and search for **SolarEdge One EV Charger**.

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

| Command | Effect | Status on tested firmware |
|---------|--------|---------------------------|
| `curr <mA>` | Set charging current limit (6000–16000) | ✅ works; `0` does not pause a session |
| `setenergy <0.1 Wh>` | Per-session energy target (0 = no limit), not used by this integration | ❌ value is accepted, but a session is not stopped |
| `ena 1` / `ena 0` | Enable / disable charging, not used by this integration | ❌ no effect on any tested firmware |
| `xswitchphase 1` / `xswitchphase 3` | Switch to 1-phase / 3-phase mode | ❌ no effect (tested with an active session) |
| `unlock` | Release the cable lock | ⚠️ accepted, no effect during a session; not tested while idle |
| `currtime <mA> <s>` | Per the KEBA guide: apply the current after `<s>` seconds, not permanent (reset when the plug is pulled); `currtime 0 1` should stop charging. Not used by this integration | ❌ no lasting effect on FW 04.00.70: `currtime 12000 10` is acknowledged but ignored, `currtime 0 1` pauses for about 15 s and charging then resumes by itself |

Details and sources are in the next section.

### Which write commands actually work

The raw test data and the method are in [docs/hardware-tests.md](docs/hardware-tests.md).

Write support depends on the firmware. What has been observed so far (read-only
access always works):

| Command | SolarEdge ONE, FW 04.00.70 (maintainer, also in an active session) | SolarEdge ONE EV, FW 04.00.42 (#12, also in an active session) |
|---------|------------------------------|------------------------------|
| `curr` (6000–16000) | ✅ `TCH-OK`, current follows (14.7 → 9.95 A); 1–5999 is ignored; `0` pauses only ~10 s | ✅ value stays, the real current follows it; `0` pauses only for a few seconds |
| `setenergy` | ✅ `TCH-OK`, value stays | ❌ interrupts charging for 4–7 s, then it resumes |
| `ena` | ❌ empty reply, no effect | ❌ ignored, also in a session |
| `xswitchphase` | ❌ empty reply, phases unchanged in a session | not re-tested |
| `currtime <mA> <s>` | ❌ `currtime 12000 10`: `TCH-OK`, but `Curr timer` / `Tmo CT` / `Curr user` unchanged and no effect for 45 s; `currtime 0 1`: paused about 15 s, then charging resumed by itself | ❌ `currtime 0 1` paused for a few seconds, then full current returned |

A second user with the same firmware as the maintainer (04.00.70, #10) saw
`curr` between 6 and 16 A change the real current in an active session, while
`curr 0`, `ena`, `setenergy` and `xswitchphase` showed no visible effect. That
test may have been confounded by the car's own cloud control and is being
repeated. Not verified yet with a car connected: whether `xswitchphase`
switches the phases. A session cannot be stopped through this interface on
the firmware tested so far; stop it from the car or its app.

In #12 the user also saw that with the back office set to "Use Offline" the
charger stops answering UDP, and that "Other Backoffice" (own OCPP server) keeps
local settings. The `Backend Connected` diagnostic sensor shows whether a back
office is attached. See [issue #10](https://github.com/mousehome-net/keba_one_ev/issues/10)
and [issue #12](https://github.com/mousehome-net/keba_one_ev/issues/12).

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
| SolarEdge ONE EV Charger (KEBA P30 OEM), maintainer | 04.00.70 | ✅ Reading works; `curr` and `setenergy` verified (no car connected) |
| SolarEdge ONE EV (EV Pro), user report in [#12](https://github.com/mousehome-net/keba_one_ev/issues/12) | 04.00.42 | ✅ Reading works; `curr` verified in an active session |
| SolarEdge ONE EV Charger (`ONE_EV`), user report in [#10](https://github.com/mousehome-net/keba_one_ev/issues/10) | 04.00.70 | ✅ Reading works; `curr` verified in an active session |
| SolarEdge ONE EV Charger (KEBA P30 OEM) — community confirmed | 04.00.44 | ✅ Working |
| SolarEdge Home EV Charger `KC-P30-EC2404B2-E00-SL` (single-phase), user report in [#5](https://github.com/mousehome-net/keba_one_ev/issues/5) | P30 v3.10.53 | ✅ Setup works, entities have values (DSW1.3 ON, over WiFi) |

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

## Contributing Translations

The integration ships with English (`en`) and German (`de`). To add a new language:

1. Copy `custom_components/keba_one_ev/translations/en.json` to `translations/<lang>.json`  
   (use the [BCP 47 language tag](https://www.iana.org/assignments/language-subtag-registry), e.g. `fr`, `nl`, `pl`).
2. Translate all `name` and `state` values — keep all keys unchanged.
3. Open a pull request. No code changes required.

---

## Related Integrations

This integration covers the EV charger only.
For the SolarEdge inverter (Modbus TCP), use the excellent
[solaredge-modbus-multi](https://github.com/WillCodeForCats/solaredge-modbus-multi) HACS integration.

---

## License

MIT
