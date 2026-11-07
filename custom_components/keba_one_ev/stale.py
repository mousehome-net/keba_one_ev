"""Keep the last values over isolated failed polls (issue #5).

On a WiFi link with high latency a poll occasionally fails even though the
charger is fine. Failing the update would mark every entity unavailable for a
whole cycle, so the last values are kept for up to MAX_STALE_POLLS failed polls
in a row. A charger that is really off still becomes unavailable shortly after.
"""
from __future__ import annotations

MAX_STALE_POLLS = 2


class StaleTolerance:
    """Counts consecutive failed polls and decides whether to keep old data."""

    def __init__(self, max_stale: int = MAX_STALE_POLLS) -> None:
        self._max_stale = max_stale
        self._failures = 0

    def on_success(self) -> None:
        self._failures = 0

    def on_failure(self, has_previous: bool) -> bool:
        """Return True if the previous data should be kept for this poll."""
        self._failures += 1
        return has_previous and self._failures <= self._max_stale
