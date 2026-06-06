"""Exponential backoff retry wrapper."""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from typing import Any, TypeVar

from agira.observability.errors import AgiraError, ToolError

T = TypeVar("T")


def retry_with_backoff(
    fn: Callable[..., T],
    *args: Any,
    max_retries: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 30.0,
    jitter: bool = True,
    retryable: tuple[type[Exception], ...] = (ToolError, OSError, ConnectionError),
    **kwargs: Any,
) -> T:
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            return fn(*args, **kwargs)
        except retryable as exc:
            last_exc = exc
            if attempt >= max_retries:
                break
            delay = min(base_delay * (2**attempt), max_delay)
            if jitter:
                delay *= 0.5 + random.random()
            time.sleep(delay)
    raise ToolError(
        f"Operation failed after {max_retries + 1} attempts",
        details={"last_error": str(last_exc)},
    ) from last_exc
