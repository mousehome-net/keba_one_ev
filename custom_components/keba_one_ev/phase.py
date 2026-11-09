"""Active phase mode from KEBA report 2 ("X2 phaseSwitch").

The phase mode can only be read. Changing it over UDP does not work on the
SolarEdge ONE firmware (neither `xswitchphase` nor the documented `x2src`/`x2`);
the SolarEdge app switches it through the cloud back office, and the value read
here follows that setting.
"""
from __future__ import annotations

# Machine-readable keys, labels come from translations/*.json
PHASE_OPTIONS = ["1_phase", "3_phase"]

# 2 is reported by some hardware variants and treated as single-phase.
_PHASE_FROM_INT = {1: "1_phase", 2: "1_phase", 3: "3_phase"}


def phase_mode(phase_switch: int | None) -> str | None:
    """Return "1_phase" or "3_phase", or None for any other value.

    None covers e.g. 0 on single-phase units without a phase switch (issue #5).
    """
    return _PHASE_FROM_INT.get(phase_switch)
