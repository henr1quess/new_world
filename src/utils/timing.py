"""Utility helpers for timing-related operations."""

from __future__ import annotations

import random
import time


def sleep_ms(ms: int, jitter: float = 0.25) -> None:
    """Sleep for ``ms`` milliseconds with a human-like jitter."""
    if ms < 0:
        raise ValueError("ms must be non-negative")
    if jitter < 0:
        raise ValueError("jitter must be non-negative")

    jitter_window = ms * jitter
    duration_ms = max(0.0, (ms - jitter_window) + random.random() * (2 * jitter_window))
    time.sleep(duration_ms / 1000.0)
