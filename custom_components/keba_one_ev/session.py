"""Session duration derived from KEBA report 100 (issue #6).

`started[s]` and `ended[s]` are Unix epoch timestamps, not elapsed
time -- report 100 also contains a matching human-readable string
("started": "2026-11-01 10:50:45.098Z") confirming this. The actual
session duration has to be computed from the gap between start and end
(or between start and now, while the session is still running), not
read directly off either field.
"""
from __future__ import annotations


def session_duration_s(started: int, ended: int, now: float) -> int:
    """Seconds elapsed in the current/last charging session.

    Returns 0 if no session has started yet. Uses `ended` when the
    session has finished, otherwise `now` for an ongoing session.
    Clamped to 0 to tolerate clock skew between charger and HA host.
    """
    if not started:
        return 0
    end = ended if ended else now
    return max(0, int(end - started))
