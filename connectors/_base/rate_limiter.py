"""
Shared leaky bucket rate limiter for connector API calls.
"""
from __future__ import annotations

import threading
import time


class RateLimiter:
    """
    Leaky bucket rate limiter.

    Usage:
        limiter = RateLimiter(rpm=60)  # 60 requests per minute
        limiter.acquire()              # blocks until a slot is available
    """

    def __init__(self, rpm: int = 60):
        self._rpm = rpm
        self._min_interval = 60.0 / rpm  # seconds between requests
        self._last_call: float = 0.0
        self._lock = threading.Lock()

    def acquire(self) -> None:
        """Block until a request slot is available."""
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_call
            if elapsed < self._min_interval:
                time.sleep(self._min_interval - elapsed)
            self._last_call = time.monotonic()

    @property
    def rpm(self) -> int:
        return self._rpm
