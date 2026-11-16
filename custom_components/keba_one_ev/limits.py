"""Range of the charging-current setting (issue #3).

`Curr HW` in report 2 is, per KEBA's guide, the minimum of the DIP switch
setting, the cable coding and the temperature monitoring (6000-32000 mA, or
0). The charger itself caps the offered current at this value (verified: with
Curr HW 16000, `curr 17000` left Max curr at 16000), so it is a safe upper
limit for the slider. For 0 or implausible values the previous fixed 16 A is
used.
"""
from __future__ import annotations

MIN_CURRENT_MA = 6000
FALLBACK_MAX_MA = 16000
_HW_RANGE = range(6000, 32001)


def max_current_ma(curr_hw_ma: int | None) -> int:
    """Upper limit for the current setting in mA."""
    if curr_hw_ma in _HW_RANGE:
        return curr_hw_ma
    return FALLBACK_MAX_MA


def clamp_current_ma(requested_ma: int, curr_hw_ma: int | None) -> int:
    """Clamp a requested current to 6 A .. the hardware limit."""
    return max(MIN_CURRENT_MA, min(max_current_ma(curr_hw_ma), requested_ma))
