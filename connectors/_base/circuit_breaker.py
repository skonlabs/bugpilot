"""
Shared circuit breaker for use outside ConnectorBase (e.g. direct API calls).
ConnectorBase has its own built-in _CircuitBreaker; this module exposes a
standalone version for other uses.
"""
from __future__ import annotations

import time
from typing import Optional


class CircuitBreaker:
    """
    3 failures → open for 300 seconds, then auto-reset.
    Thread-safe for single-process use.
    """

    THRESHOLD = 3
    TIMEOUT = 300  # seconds

    def __init__(self, name: str, threshold: int = 3, timeout: int = 300):
        self.name = name
        self.THRESHOLD = threshold
        self.TIMEOUT = timeout
        self._failures = 0
        self._opened_at: Optional[float] = None

    def is_open(self) -> bool:
        if self._failures >= self.THRESHOLD:
            if self._opened_at and (time.time() - self._opened_at) < self.TIMEOUT:
                return True
            self._failures = 0  # Reset after timeout
        return False

    def record_success(self) -> None:
        self._failures = 0

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self.THRESHOLD:
            self._opened_at = time.time()

    @property
    def failure_count(self) -> int:
        return self._failures
