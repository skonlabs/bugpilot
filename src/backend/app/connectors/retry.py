"""
Retry helper with exponential backoff for async connector calls.
"""
from __future__ import annotations

import asyncio
import functools
import random
import time
from typing import Any, Callable, Optional, Type, Tuple

import structlog

logger = structlog.get_logger(__name__)


def async_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    jitter: bool = True,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    retryable_status_codes: Tuple[int, ...] = (429, 500, 502, 503, 504),
) -> Callable:
    """
    Async retry decorator with exponential backoff.

    Args:
        max_attempts: Maximum number of total attempts (including the first).
        base_delay: Base delay in seconds for backoff calculation.
        jitter: Whether to add random jitter to the backoff delay.
        retryable_exceptions: Exception types that should trigger a retry.
        retryable_status_codes: HTTP status codes that should trigger a retry
            (only applicable when exceptions carry a .response attribute, e.g. httpx).

    Raises:
        The last exception raised after all attempts are exhausted.
    """

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc: Optional[Exception] = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return await fn(*args, **kwargs)

                except retryable_exceptions as exc:
                    last_exc = exc
                    retry_after: Optional[float] = None

                    # Try to extract Retry-After from httpx response if available
                    response = getattr(exc, "response", None)
                    if response is not None:
                        status_code = getattr(response, "status_code", None)

                        # If this is a non-retryable status code, re-raise immediately
                        if (
                            status_code is not None
                            and status_code not in retryable_status_codes
                            and status_code >= 400
                        ):
                            raise

                        if status_code == 429:
                            retry_after_header = response.headers.get("Retry-After")
                            if retry_after_header is not None:
                                try:
                                    retry_after = float(retry_after_header)
                                except (ValueError, TypeError):
                                    pass

                    if attempt >= max_attempts:
                        logger.error(
                            "retry_exhausted",
                            function=fn.__qualname__,
                            attempt=attempt,
                            max_attempts=max_attempts,
                            error=str(exc),
                        )
                        raise

                    # Compute delay
                    if retry_after is not None:
                        delay = retry_after
                    else:
                        # Exponential backoff: base_delay * 2^(attempt-1)
                        delay = base_delay * (2 ** (attempt - 1))

                    if jitter:
                        # Add up to 25% random jitter
                        delay += random.uniform(0, delay * 0.25)

                    logger.warning(
                        "retry_attempt",
                        function=fn.__qualname__,
                        attempt=attempt,
                        max_attempts=max_attempts,
                        delay_seconds=round(delay, 3),
                        error=str(exc),
                    )

                    await asyncio.sleep(delay)

            # Should never reach here, but just in case
            if last_exc is not None:
                raise last_exc

        return wrapper

    return decorator


__all__ = ["async_retry"]
