"""Polling sequence for the four KEBA reports (issue #8).

KEBA chargers need a short pause between consecutive UDP requests
(t_UDP_pause in the KEBA UDP programming manual); sending four requests
back to back can make the charger silently drop one. Since report 2 and
report 3 are mandatory for the coordinator (see coordinator.py), a
single dropped reply would otherwise take every entity Unavailable, so
those two get one retry before giving up.
"""
from __future__ import annotations

import time
from typing import Callable

REPORT_PAUSE_S = 0.5


def fetch_all(
    send: Callable[[str], dict | None],
    sleep: Callable[[float], None] = time.sleep,
) -> tuple[dict | None, dict | None, dict | None, dict | None]:
    """Fetch reports 1, 2, 3, 100 with a pause between requests.

    `send` takes a KEBA command string and returns the parsed reply, or
    None on timeout/error. Reports 2 and 3 get one retry; 1 and 100 are
    best-effort and are not retried.
    """
    r1 = send("report 1")
    sleep(REPORT_PAUSE_S)
    r2 = _send_with_retry(send, sleep, "report 2")
    sleep(REPORT_PAUSE_S)
    r3 = _send_with_retry(send, sleep, "report 3")
    sleep(REPORT_PAUSE_S)
    r100 = send("report 100")
    return r1, r2, r3, r100


def _send_with_retry(
    send: Callable[[str], dict | None],
    sleep: Callable[[float], None],
    command: str,
) -> dict | None:
    result = send(command)
    if result is None:
        sleep(REPORT_PAUSE_S)
        result = send(command)
    return result
