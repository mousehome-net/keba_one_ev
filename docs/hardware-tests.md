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

## Community results

| Source | Unit | Result |
|--------|------|--------|
| [#12](https://github.com/mousehome-net/keba_one_ev/issues/12) | SolarEdge ONE EV (EV Pro), FW 04.00.42, back office attached | `curr 10000` held in all states (no car, car without session, active session at 10.6 kW); current fell from about 15 A to about 9.5 A and came back after restoring. `ena 0` / `ena 1`: no reply (resp. empty reply), no effect. `currtime 0 1`: `TCH-OK`, current fell to about 0.1–0.8 A and was back at about 15 A after 6 s with no further command. `curr 0` in a session: dipped to about 0.6 A, full again after about 6 s, `Curr user` stayed 16000. `setenergy 4508` (below the 9017 already delivered): `State 5`, then `State 2`, charging resumed after 4–7 s, `Setenergy` stayed 4508. |
| [#10](https://github.com/mousehome-net/keba_one_ev/issues/10) | ONE_EV, FW 04.00.70 | `curr 10000` accepted, `Curr user` 10000. In a session `curr` between 6 and 16 A changed the current; `curr 0`, `ena`, `setenergy` and `xswitchphase` showed no visible effect, possibly masked by the car's own cloud control (retest announced). |
| [#5](https://github.com/mousehome-net/keba_one_ev/issues/5) | `KC-P30-EC2404B2-E00-SL`, FW P30 v3.10.53, single-phase | Setup works. `report 1`, `2`, `3` and `100` answer; 30 of 30 back-to-back requests succeeded. `X2 phaseSwitch` is 0 (no phase switch). |

## Conclusions so far

- `curr` (6000–16000 mA) is the only control that works reliably, also in a
  session.
- No tested command stops a session for good: `ena` is ignored, `curr 0` and
  `currtime 0 <s>` only pause for a few seconds, `setenergy` below the
  delivered energy only interrupts for 4–7 s.
- `xswitchphase` had no effect on FW 04.00.70 in a session. One report from
  FW 04.00.42 (#12) says it was accepted and reset within seconds, which has not
  been re-tested.
- `unlock` is acknowledged but ignored while a session is running.

## Not tested yet

- `unlock` while the vehicle is connected but not charging (`State 2`): does
  `Plug` change from 7 to 5?
- `xswitchphase` on other firmware versions, in a session.
- Long-running automatic current changes, and how different cars react.

## Background from the KEBA documentation

Taken from the KEBA UDP Programmers Guide V2.01 as quoted in search results;
the full text of these sections was not read, so treat the details as
unverified:

- `Curr user` accepts `0` or `6000`–`63000` mA, which matches the 6 A lower
  limit seen in the tests (`curr 3000` is ignored).
- The guide recommends `currtime` over `curr` for adjusting the current, since
  `curr` overwrites `Curr user` directly. The reasoning was cut off in the source
  and may concern more than storage; check it before building an automation that
  writes `curr` often.
- Current changes during a session are applied with a delay of a few seconds
  (3 s were measured here).
