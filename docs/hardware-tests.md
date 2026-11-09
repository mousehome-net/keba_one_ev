# Hardware tests

Results of testing the KEBA UDP commands on real chargers. The README only
shows the summary; this file keeps the method and the raw values so the results
can be checked and repeated. Community results link to the issue they came from.

## Method

Commands were sent directly over UDP to port 7090 (not through the
integration) from a host on the charger's network, and read back with
`report 2` (state, limits) and `report 3` (currents, power):

```
echo -n "curr 10000" | nc -u -w3 <charger-ip> 7090
echo -n "report 3"   | nc -u -w2 <charger-ip> 7090
```

After every test the original values were restored. A command counts as
"working" only if the read-back shows the effect, a `TCH-OK` reply alone is not
enough.

## Maintainer's unit

SolarEdge ONE EV Charger, product `ONE_EV`, firmware `04.00.70`,
`Backend: 1`, 3-phase, hardware limit 16 A.

### 2026-11-06, no vehicle (`Plug 1`, `State 1`)

| Command | Reply | Read-back |
|---------|-------|-----------|
| `curr 10000` | `TCH-OK: done` | `Curr user` 10000, unchanged after 30 s |
| `curr 0` | `TCH-OK: done` | `Curr user` 0 |
| `curr 3000` | empty | ignored, `Curr user` stays 0 |
| `curr 16000` | `TCH-OK: done` | restored |
| `setenergy 50000` | `TCH-OK: done` | `Setenergy` 50000, unchanged after 20 s |
| `ena 0` / `ena 1` | empty | `Enable user` stays 1 |
| `xswitchphase 1` / `3` | empty | `X2 phaseSwitch` stays 3 |

### 2026-11-09, active session (`Plug 7`, `State 3`, about 14.7 A per phase, 9.9 kW)

| Test | Observation |
|------|-------------|
| `curr 10000` | `TCH-OK`. Current fell from 14.7 A to 9.95 A and power from 9.94 kW to 6.68 kW within 3 s, stayed there for 30 s, `Max curr` followed (10000). After `curr 16000` back to 14.8 A within 3 s. |
| `curr 0` | `TCH-OK`. After 2 s about 0.05 A and `State 2`. From about 12 s charging started again by itself (`State 3`), full 14.75 A at 20 s, before any command from us. `Curr user` stayed 16000 throughout. Without a vehicle the same command had set `Curr user` to 0. |
| `xswitchphase 1` | Empty reply. All three phases stayed at about 14.7 A and `X2 phaseSwitch` stayed 3 for about 70 s (samples every 4–8 s). The session was not interrupted. |
| `unlock` | `TCH-OK`. `Plug` stayed 7 (cable locked) and charging continued for 25 s. |
| `x2src 4`, then `x2 0` (the phase switch as documented by KEBA) | Both replies empty. `X2 phaseSwitch` stayed 3 and all three phases kept carrying current (about 10 A, later 6 A) for over 3 minutes. The guide describes `x2` as triggering an *external* phase switch via contact X2; whether this unit has one is unknown. `report 2` on this firmware has no `X2 phaseSwitch source` field. |
| `currtime 0 1` | `TCH-OK`. Current fell to 0.05 A and `State` to 2 for about 15 s, then charging started again by itself (`State 3` at about 23 s, 13.7 A at about 28 s). `Curr user`, `Curr timer`, `Tmo CT` and `Enable user` never changed and no further command was sent. The KEBA guide describes this command as a stop until overwritten. |
| `currtime 12000 10` | `TCH-OK`, but nothing happened: `Curr timer` stayed 16000, `Tmo CT` stayed 0, `Curr user`, `Max curr` and the current stayed unchanged for 45 s (samples every ~5 s). According to the KEBA guide `Curr user` should have become 12000 after 10 s. |

### 2026-11-09, validation of two assumptions (active session)

- **`Max curr %` is the control pilot duty cycle in units of 0.1 %**, not a
  percentage of the limit. Measured: `266` at 16 A and `166` at 10 A; the pilot
  formula (duty % = A / 0.6) gives 26.7 % and 16.7 %, and the idle value `1000`
  (100 %) is the state without a pilot signal.
- **The charger caps the offered current at `Curr HW`.** With `Curr HW` 16000,
  `curr 17000` was acknowledged and `Curr user` became 17000, but `Max curr`
  stayed 16000, `Max curr %` stayed 266 and the phase currents did not change
  over 20 s. So `Max curr` is the minimum of `Curr user` and `Curr HW`, which makes
  `Curr HW` a safe upper limit for a current setting. Not covered: units with
  `Curr HW` above 16000, and states in which `Curr HW` reads 0 (the guide allows
  0).

- **A `curr` setting is not reset by the failsafe function.** The reports show
  `Tmo FS` 119 and `Curr FS` 16000, which would drop the current back to 16 A
  after about two minutes without a command if the failsafe were active. `curr
  10000` was sent once and held for 230 s without any further command:
  `Curr user` and `Max curr` stayed 10000, `Enable sys` stayed 1, the phase current
  stayed at about 9.9 A. So no periodic re-sending is needed on this unit.

### 2026-11-09, no vehicle: how the SolarEdge app switches phases

**Network of the charger** (nmap from the LAN, firewall state table of the router):

- No TCP port is open: all 65 535 TCP ports answer "closed". No web server, no
  REST API, no Modbus TCP (port 502 is closed).
- UDP: only 7090 (KEBA protocol) and 5353 (mDNS, which only returns the host name).
- The charger holds exactly one long-lived outbound connection: TCP to an AWS host
  in Frankfurt on port 443 whose TLS certificate is `*.wevo.energy`. This matches
  the SolarEdge guide, which lists "Wevo Energy" as a back office option, and the
  `RFID tag` value `weev_dummy` in `report 100`.

**Phase switch in the SolarEdge app (3 → 1 phase):** between two polls
(`X2 phaseSwitch` 3 at 12:04:58, 1 at 12:05:41) both `X2 phaseSwitch` and
`X2 default` changed from 3 to 1, so it is a stored setting. During the switch no
new connection to the charger appeared in the firewall state table: the app does
not talk to the charger locally, the command takes the existing cloud
connection. The app kept working after `x2src 4` had been sent earlier, so that
command did not take over phase control.

**UDP `x2 1` (back to 3 phases), vehicle not connected, more than 5 minutes after
the switch (the guide requires 5 minutes between switches):** empty reply,
`X2 phaseSwitch` stayed 1 for 60 s. So the documented UDP phase switch does not
work on this firmware, neither in a session nor when idle.

### 2026-11-09, which commands does the firmware know?

Made-up commands (`foobar`, `zzz 1`, `report 99`) get an **immediate empty reply**
(0.00 s), while recognised commands answer `TCH-OK: done` or JSON. By that pattern,
on FW 04.00.70:

- recognised: `curr`, `currtime`, `setenergy`, `unlock`, `report 1/2/3/100`
  (`currtime`, `setenergy` and `unlock` are recognised but do not behave as KEBA
  documents, see above);
- answered like an unknown command: `ena`, `x2src`, `x2`, `xswitchphase`.

This is an inference from the reply pattern, not a confirmed list. Probing further
names this way is possible but risky: a recognised command is executed at once,
with unknown effects.

### 2026-11-09, minimum gap between two commands

KEBA requires at least 100 ms between any two UDP commands (`t_UDP_pause`) and at
least 5 s between repetitions of the same command (`t_COM_pause`). The integration
keeps 500 ms between the polled reports, but right after a control command the
refresh can send `report 1` without a gap. Tested with read commands only:
`report 2` immediately followed by `report 1`, 15 times without a gap and 15 times
with 150 ms, 6 s between rounds. All 60 requests were answered, so on this unit a
missing gap did not cause dropped replies.

### 2026-11-09, session history and other read commands

- `i` returns `{"Firmware":"04.00.70"}`.
- `report 101`, `report 102`: the last finished sessions, with `Session ID`,
  `E Pres` (energy of that session), `started[s]` / `ended[s]` (Unix epoch on this
  firmware), `started` / `ended` as UTC strings and `reason` (`1` = ended by
  unplugging). Example: session 4 from 10:34:08 to 11:51:42 UTC, 10.38 kWh.
  `report 130` returned an empty reply (no entry).
- After unplugging, `report 100` already shows the next, empty session
  (`started[s]` 0) while `E Pres` keeps the last session's value.
- Note: KEBA's guide defines `started[s]` / `ended[s]` as seconds since the last
  restart of the charger, not as Unix time. On this firmware they are Unix time;
  a genuine P30 may follow the guide. Not checked on a P30 yet.
- Not tested: the status messages of chapter 4.4 (the charger pushes changes of
  `State`, `Plug`, `Enable sys`, `Max curr`, `E pres` to the address of the last
  command). This needs a vehicle to trigger changes.

## Community results

| Source | Unit | Result |
|--------|------|--------|
| [#12](https://github.com/mousehome-net/keba_one_ev/issues/12) | SolarEdge ONE EV (EV Pro), FW 04.00.42, back office attached | `curr 10000` held in all states (no car, car without session, active session at 10.6 kW); current fell from about 15 A to about 9.5 A and came back after restoring. `ena 0` / `ena 1`: no reply (resp. empty reply), no effect. `currtime 0 1`: `TCH-OK`, current fell to about 0.1–0.8 A and was back at about 15 A after 6 s with no further command. `curr 0` in a session: dipped to about 0.6 A, full again after about 6 s, `Curr user` stayed 16000. `setenergy 4508` (below the 9017 already delivered): `State 5`, then `State 2`, charging resumed after 4–7 s, `Setenergy` stayed 4508. |
| [#10](https://github.com/mousehome-net/keba_one_ev/issues/10) | ONE_EV, FW 04.00.70 | `curr 10000` accepted, `Curr user` 10000. In a session `curr` between 6 and 16 A changed the current; `curr 0`, `ena`, `setenergy` and `xswitchphase` showed no visible effect, possibly masked by the car's own cloud control (retest announced). |
| [#5](https://github.com/mousehome-net/keba_one_ev/issues/5) | `KC-P30-EC2404B2-E00-SL`, FW P30 v3.10.53, single-phase | Setup works. `report 1`, `2`, `3` and `100` answer; 30 of 30 back-to-back requests succeeded. `X2 phaseSwitch` is 0 (no phase switch). |

## Conclusions so far

- `curr` (6000–16000 mA) is the only control that works reliably, also in a
  session.
- No tested command stops a session for good: `ena` is ignored, `curr 0` pauses
  for about 10 s, `currtime 0 1` for about 15 s (a few seconds in #12), and
  `setenergy` below the delivered energy only interrupts for 4–7 s. In every case
  charging resumes by itself.
- `currtime` is not usable here: the delayed form (`currtime 12000 10`) is
  acknowledged but ignored, so there is nothing to build on. `curr` stays the only
  way to set the current.
- Phase switching over UDP has no effect on FW 04.00.70, neither in a session nor
  when idle, neither with `xswitchphase` (not documented by KEBA) nor with the
  documented `x2src 4` + `x2 0|1`. The charger does switch phases when told to by
  the SolarEdge app, which reaches it through the cloud back office. The result is
  readable: `X2 phaseSwitch` shows the active setting.
- One report from FW 04.00.42 (#12) says `xswitchphase 1` was accepted and
  reset to 3 within seconds, which has not been re-tested.
- `unlock` is acknowledged but ignored while a session is running; the KEBA
  guide requires charging to be stopped first.

## Not tested yet

- `unlock` right after a stop, as the guide requires ("the charging process has to
  be stopped first, e.g. via `currtime 0 1` or `ena 0`").
- `unlock` while the vehicle is connected but not charging (`State 2`): does
  `Plug` change from 7 to 5?
- `xswitchphase` on other firmware versions, in a session.
- Long-running automatic current changes, and how different cars react.

## Background from the KEBA documentation

From the KEBA KeContact P30 UDP Programmers Guide V 2.05 (full text kept locally,
not in this repository):

- `curr <mA>` and `currtime <mA> <s>` accept `0` or `6000`–`63000` mA, which
  matches the 6 A lower limit seen here (`curr 3000` is ignored). `Max curr`, the
  value offered to the vehicle, is limited to `0` or `6000`–`32000` mA. The guide
  ties this to the control pilot signal of IEC 61851-1: the charger only
  communicates a maximum allowed current, the vehicle controls the actual one.
- `currtime [c] [t]` sets the current `c` after a delay of `t` seconds (`t` is a
  delay, not a duration). The change is not permanent and is reset when the plug
  is pulled. `currtime 0 1` is described as a charging stop similar to `ena 0`
  that lasts until a new `currtime` overwrites it. This is **not** what was
  observed on the SolarEdge ONE firmware: `currtime 12000 10` had no effect at all
  here, and `currtime 0 1` only paused for a few seconds in #12.
- `curr` changes `Curr user` immediately and is "permanent until the device is
  rebooted". The guide advises against it because such a setting can only be
  removed by a reboot or by overwriting it with `currtime`. The guide does not
  mention flash wear. Since `currtime` does not work on this firmware, `curr` is
  the only usable way to set the current.
- A current change during a session is executed after a delay of 6–7 seconds
  (IEC 61851-1 requires a minimum time between changes), and a second request in
  that window overwrites the target without restarting the timer. About 3 s were
  measured here.
- `unlock` only works after charging has been stopped (e.g. `currtime 0 1` or
  `ena 0`), so the result with a running session is expected.
- The documented phase switch is `x2src <0-4>` (4 = toggle via UDP) followed by
  `x2 0|1`, with a 5 minute cool-down between switches. `xswitchphase` appears in
  neither the UDP nor the Modbus TCP guide.
- `ena` and `curr` are listed as commands "with permanent effects" that should
  not be used regularly, as they change the behaviour until overwritten or the
  device is rebooted. The failsafe function (`failsafe <t> <c> <s>`) drops the
  current to `c` if no `curr`, `currtime` or `ena` arrives within `t` seconds. It
  is off by default.
- `setenergy` is described as a limit that stops the session and deactivates the
  device like `ena 0` once reached, and as non-permanent. That is not what the
  SolarEdge firmware does (charging resumes after 4–7 s, #12).
- `Curr HW` is "the minimum of the DIP switch settings, cable coding and
  temperature monitoring" and ranges from 6000 to 32000 mA, which is the right
  source for the upper limit of a current setting (see #3).
- `Max curr %` is the duty cycle of the control pilot signal in units of 0.1 %
  (`266` = 26.6 %, which corresponds to 16 A), not a percentage of the current
  limit.
