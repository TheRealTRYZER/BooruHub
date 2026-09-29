"""In-memory sliding window rate limiter for FastAPI.

Usage as a dependency:
    @router.post("/login")
    async def login(..., _rl=Depends(rate_limit("login", max_requests=10, window_seconds=60))):
"""
import time
import asyncio
import ipaddress
from collections import defaultdict
from typing import Optional

from fastapi import Request, HTTPException, status

from app.core.config import get_settings


# Networks whose members are treated as reverse proxies even when they are not
# listed in TRUSTED_PROXY_IPS. This covers the bundled nginx (same private
# Docker network) and local development. The ranges are spelled out rather
# than derived from ipaddress.is_private, because Python also classifies the
# documentation ranges (192.0.2.0/24, 198.51.100.0/24, 203.0.113.0/24) as
# private, and those must never be trusted as a proxy.
IMPLICIT_PROXY_NETWORKS = tuple(
    ipaddress.ip_network(cidr)
    for cidr in ("127.0.0.0/8", "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")
)


def _is_valid_ip(ip: str) -> bool:
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False


def _is_trusted_peer(remote_addr: str) -> bool:
    """Return True when the direct peer is a proxy allowed to supply client IPs.

    A peer is trusted when it is listed in TRUSTED_PROXY_IPS (as a single
    address or a CIDR block) or falls in one of IMPLICIT_PROXY_NETWORKS. The
    backend port is never published, so a request arriving straight from the
    internet always has a public peer address and is never treated as a proxy.
    """
    if not _is_valid_ip(remote_addr):
        return False

    settings = get_settings()
    if remote_addr in set(settings.trusted_proxy_ip_list):
        return True

    ip = ipaddress.ip_address(remote_addr)
    if any(ip in net for net in settings.trusted_proxy_networks):
        return True
    return any(ip in net for net in IMPLICIT_PROXY_NETWORKS)


class _SlidingWindow:
    """Per-key sliding window counter with automatic cleanup."""

    __slots__ = ("_windows", "_lock", "_max_keys")

    def __init__(self, max_keys: int = 10000) -> None:
        self._windows: dict[str, list[float]] = defaultdict(list)
        self._lock: Optional[asyncio.Lock] = None
        self._max_keys = max_keys

    async def check(self, key: str, max_requests: int, window_seconds: int) -> bool:
        """Return True if the request is allowed, False if rate-limited."""
        if self._lock is None:
            self._lock = asyncio.Lock()

        now = time.monotonic()
        cutoff = now - window_seconds

        async with self._lock:
            timestamps = self._windows[key]
            # Prune old entries
            pruned_timestamps = [t for t in timestamps if t > cutoff]

            if len(pruned_timestamps) >= max_requests:
                if pruned_timestamps:
                    self._windows[key] = pruned_timestamps
                else:
                    self._windows.pop(key, None)
                return False

            pruned_timestamps.append(now)
            self._windows[key] = pruned_timestamps

            # Evict oldest keys if we have too many (B-M2)
            if len(self._windows) > self._max_keys:
                # 1. Prune all empty/expired keys first
                for k in list(self._windows.keys()):
                    self._windows[k] = [t for t in self._windows[k] if t > cutoff]
                    if not self._windows[k]:
                        self._windows.pop(k, None)

                # 2. If still over limit, evict keys that are out of their window
                if len(self._windows) > self._max_keys:
                    candidates = [
                        k for k, v in self._windows.items()
                        if not v or now - v[-1] > window_seconds
                    ]
                    if candidates:
                        oldest_key = min(candidates, key=lambda k: self._windows[k][-1] if self._windows[k] else 0)
                        del self._windows[oldest_key]

            return True


# Singleton instance shared across all rate limiters
_window = _SlidingWindow()


def _get_client_ip(request: Request) -> str:
    """Extract the client IP for rate-limit bucketing.

    Proxy headers are only consulted when the direct peer is a trusted proxy,
    so a client cannot rotate its bucket by forging a header. X-Real-IP is
    preferred because nginx sets it to a single $remote_addr value; the
    X-Forwarded-For leftmost entry is used as a fallback for other setups.
    """
    remote_addr = request.client.host if request.client else "unknown"
    if not _is_valid_ip(remote_addr):
        return "127.0.0.1"

    if _is_trusted_peer(remote_addr):
        for header in ("x-real-ip", "x-forwarded-for"):
            forwarded = request.headers.get(header)
            if not forwarded:
                continue
            first_ip = forwarded.split(",")[0].strip()
            if _is_valid_ip(first_ip):
                return first_ip

    return remote_addr


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
