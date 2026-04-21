"""In-memory sliding window rate limiter for FastAPI.

Usage as a dependency:
    @router.post("/login")
    async def login(..., _rl=Depends(rate_limit("login", max_requests=10, window_seconds=60))):
"""
import time
import asyncio
from collections import defaultdict
from typing import Optional

from fastapi import Request, HTTPException, status


class _SlidingWindow:
    """Per-key sliding window counter with automatic cleanup."""

    __slots__ = ("_windows", "_lock", "_max_keys")

    def __init__(self, max_keys: int = 10000) -> None:
        self._windows: dict[str, list[float]] = defaultdict(list)
        self._lock = asyncio.Lock()
        self._max_keys = max_keys

    async def check(self, key: str, max_requests: int, window_seconds: int) -> bool:
        """Return True if the request is allowed, False if rate-limited."""
        now = time.monotonic()
        cutoff = now - window_seconds

        async with self._lock:
            timestamps = self._windows[key]
            # Prune old entries
            self._windows[key] = [t for t in timestamps if t > cutoff]
            timestamps = self._windows[key]

            if len(timestamps) >= max_requests:
                return False

            timestamps.append(now)

            # Evict oldest keys if we have too many
            if len(self._windows) > self._max_keys:
                oldest_key = min(self._windows, key=lambda k: self._windows[k][-1] if self._windows[k] else 0)
                del self._windows[oldest_key]

            return True


# Singleton instance shared across all rate limiters
_window = _SlidingWindow()


def _get_client_ip(request: Request) -> str:
    """Extract client IP, respecting X-Forwarded-For behind a reverse proxy."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def rate_limit(
    name: str,
    max_requests: int = 30,
    window_seconds: int = 60,
    key_func: Optional[callable] = None,
):
    """Create a FastAPI dependency that enforces rate limiting.

    Args:
        name: Logical name for the rate limit group (e.g. "login", "search")
        max_requests: Maximum requests allowed in the window
        window_seconds: Sliding window duration in seconds
        key_func: Optional function(request) -> str for custom key extraction.
                  Defaults to client IP.
    """

    async def _dependency(request: Request) -> None:
        if key_func:
            key = key_func(request)
        else:
            key = _get_client_ip(request)

        rate_key = f"{name}:{key}"
        allowed = await _window.check(rate_key, max_requests, window_seconds)

        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Try again in {window_seconds} seconds.",
            )

    return _dependency
