"""Token-bucket rate limiter for external operations."""

from __future__ import annotations

import threading
import time


class RateLimiter:
    def __init__(self, rate: float = 10.0, capacity: float = 20.0) -> None:
        self.rate = rate
        self.capacity = capacity
        self._tokens = capacity
        self._last = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self, tokens: float = 1.0) -> None:
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last
            self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)
            self._last = now
            if self._tokens < tokens:
                wait = (tokens - self._tokens) / self.rate
                time.sleep(wait)
                self._tokens = 0.0
            else:
                self._tokens -= tokens
