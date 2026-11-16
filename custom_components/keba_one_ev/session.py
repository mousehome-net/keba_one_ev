"""Session times derived from KEBA report 100 / 101 (issues #6, #5).

`started[s]` / `ended[s]` mean different things depending on the firmware:

- SolarEdge ONE: Unix epoch timestamps (report 100 also has the matching
  text "started": "2026-11-01 10:50:45.098Z").
- KEBA's guide (genuine P30): seconds since the charger's last restart; the
  current uptime is the `Sec` field of the same report, and the text field
  holds the UTC time if the charger could sync its clock via NTP.

Values from before 2001 are therefore treated as uptime.
"""
from __future__ import annotations

from datetime import datetime, timezone


_EPOCH_MIN = 1_000_000_000  # 2001-09-09; smaller values are uptimes


def _is_epoch(value: int | None) -> bool:
    return bool(value) and value >= _EPOCH_MIN


def session_duration_s(started: int, ended: int, now: float, uptime: int | None = None) -> int:
    """Seconds elapsed in the current/last charging session.

    Returns 0 if no session has started yet. Uses `ended` when the session
    has finished, otherwise the current time: `now` for Unix timestamps,
    the charger's uptime (`Sec`) for uptime values. Clamped to 0 to tolerate
    clock skew between charger and HA host.
    """
    if not started:
        return 0
    if ended:
        end = ended
    elif _is_epoch(started):
        end = now
    elif uptime:
        end = uptime
    else:
        return 0
    return max(0, int(end - started))


def _parse_text_time(text: str | None) -> datetime | None:
    """Parse "2026-11-05 12:16:13.853Z" as UTC; None if it is not a real date."""
    if not text:
        return None
    try:
        value = datetime.strptime(text.strip().rstrip("Z"), "%Y-%m-%d %H:%M:%S.%f")
    except ValueError:
        return None
    if value.year < 2015:
        return None
    return value.replace(tzinfo=timezone.utc)


def session_start_datetime(started: int, text: str | None = None) -> datetime | None:
    """Session start (or end) as an aware UTC datetime, None if unknown."""
    if not started:
        return None
    if _is_epoch(started):
        return datetime.fromtimestamp(started, tz=timezone.utc)
    return _parse_text_time(text)


def needs_history(current_id: int | None, fetched_for: int | None) -> bool:
    """report 101 only changes when a new session starts in report 100."""
    return current_id is not None and current_id != fetched_for


def last_session_summary(r101: dict | None) -> dict | None:
    """Energy, start, end and duration of the last finished session."""
    if not r101:
        return None
    started = r101.get("started[s]", 0)
    ended = r101.get("ended[s]", 0)
    duration = ended - started if started and ended and ended >= started else None
    return {
        "energy_kwh": round(r101.get("E Pres", 0) * 0.1 / 1000, 2),
        "started": session_start_datetime(started, r101.get("started")),
        "ended": session_start_datetime(ended, r101.get("ended")),
        "duration_s": duration,
    }
