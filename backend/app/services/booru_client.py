"""Booru client coordinator.

Sits between the API layer and individual providers.  Responsibilities:
- Per-user/per-site request pacing (rate limiting)
- Result caching with bounded LRU
- Multi-site parallel search with weighted interleaving
"""
import asyncio
import logging
import time
from collections import OrderedDict
from typing import Dict, List, Optional, Tuple

from app.db.models import User
from app.services.booru import PROVIDERS

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
#  Bounded LRU cache                                                          #
# --------------------------------------------------------------------------- #

_CACHE_MAX = 256
_CACHE_TTL = 300  # seconds

class _LRUCache:
    """Thread-safe bounded LRU cache with TTL."""

    __slots__ = ("_data", "_max")

    def __init__(self, maxsize: int = _CACHE_MAX) -> None:
        self._data: OrderedDict[tuple, tuple] = OrderedDict()
        self._max = maxsize

    def get(self, key: tuple) -> Optional[tuple]:
        entry = self._data.get(key)
        if entry is None:
            return None
        value, expiry = entry
        if time.monotonic() > expiry:
            self._data.pop(key, None)
            return None
        self._data.move_to_end(key)
        return value

    def put(self, key: tuple, value: tuple) -> None:
        if not value:
            return
        self._data[key] = (value, time.monotonic() + _CACHE_TTL)
        self._data.move_to_end(key)
        while len(self._data) > self._max:
            self._data.popitem(last=False)


_cache = _LRUCache()

# --------------------------------------------------------------------------- #
#  Per-user/per-site pacing                                                   #
# --------------------------------------------------------------------------- #

_MAX_LOCKS = 256
_user_locks: Dict[tuple, asyncio.Lock] = {}
_last_search: Dict[tuple, float] = {}


def _get_lock(key: tuple) -> asyncio.Lock:
    """Get or create a lock for the given (user_id, site) key, with bounded size."""
    if key not in _user_locks:
        if len(_user_locks) >= _MAX_LOCKS:
            # Evict oldest entry
            oldest = next(iter(_user_locks))
            del _user_locks[oldest]
            _last_search.pop(oldest, None)
        _user_locks[key] = asyncio.Lock()
    return _user_locks[key]


# --------------------------------------------------------------------------- #
#  Single-site search                                                         #
# --------------------------------------------------------------------------- #

async def search_posts(
    site: str,
    tags: str,
    limit: int = 40,
    page: int = 1,
    timeout: float = 30.0,
    user: Optional[User] = None,
    skip_interval: bool = False,
) -> Tuple[List[dict], int]:
    """Search a single booru site with caching and optional per-user pacing.
    Returns (normalised_posts, unfiltered_count).
    """
    if site not in PROVIDERS:
        logger.warning(f"Unknown provider: {site}")
        return [], 0

    # Cache lookup
    cache_key = (site, tags, limit, page, user.id if user else None)
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    provider = PROVIDERS[site]

    # Per-user pacing
    interval = getattr(user, "search_interval", 0.0) if user else 0.0
    if not skip_interval and user and interval > 0:
        lock_key = (user.id, site)
        lock = _get_lock(lock_key)

        async with lock:
            last = _last_search.get(lock_key, 0.0)
            wait = interval - (time.monotonic() - last)
            if wait > 0:
                await asyncio.sleep(wait)
            posts, count = await provider.fetch_posts(tags, page, limit, user, timeout)
            _last_search[lock_key] = time.monotonic()
    else:
        posts, count = await provider.fetch_posts(tags, page, limit, user, timeout)

    result = (posts, count)
    _cache.put(cache_key, result)
    logger.info(f"[{site}] {len(posts)} posts (tags='{tags}' page={page})")
    return result


# --------------------------------------------------------------------------- #
#  Multi-site search with weighted interleaving                               #
# --------------------------------------------------------------------------- #

async def search_multi_site(
    site_queries: Dict[str, str],
    limit: int = 40,
    page: int = 1,
    user: Optional[User] = None,
    ratios: Optional[Dict[str, float]] = None,
    skip_interval: bool = False,
) -> Tuple[List[dict], Dict[str, int]]:
    """Search multiple sites in parallel and interleave results by ratio weights.
    Returns (interleaved_posts, dict_of_unfiltered_counts_per_site).
    """
    sites = [s for s in site_queries if s in PROVIDERS and site_queries[s] is not None]
    if not sites:
        return [], {}

    # Determine per-site fetch limits
    num = len(sites)
    tasks = []
    for site in sites:
        if ratios and site in ratios:
            total_ratio = sum(ratios.values()) or 1.0
            share = ratios[site] / total_ratio
            per_site = max(20, int(limit * 3 * share))
        else:
            per_site = max(20, (limit * 2) // num)

        tasks.append(
            search_posts(
                site, site_queries[site], per_site, page,
                user=user, skip_interval=skip_interval,
            )
        )

    results = await asyncio.gather(*tasks, return_exceptions=True)

    by_site: Dict[str, List[dict]] = {}
    total_counts: Dict[str, int] = {}
    
    for i, site in enumerate(sites):
        res = results[i]
        if isinstance(res, tuple) and len(res) == 2:
            posts, count = res
            by_site[site] = posts
            total_counts[site] = count
        else:
            logger.error(f"[{site}] Multi-site error or invalid format: {res}")
            by_site[site] = []
            total_counts[site] = 0

    # Single site — no interleaving needed
    if len(sites) == 1:
        s = sites[0]
        return by_site[s][:limit], total_counts

    # Weighted interleaving algorithm
    actual_ratios = ratios or {s: 1.0 for s in sites}
    credits = {s: 0.0 for s in sites}
    iterators = {s: iter(posts) for s, posts in by_site.items() if posts}
    interleaved: List[dict] = []

    while iterators and len(interleaved) < limit * 2:
        for s in list(iterators):
            credits[s] += actual_ratios.get(s, 1.0)

        eligible = sorted(
            (s for s in iterators if credits[s] >= 1.0),
            key=lambda s: credits[s],
            reverse=True,
        )
        if not eligible:
            break

        for s in eligible:
            try:
                interleaved.append(next(iterators[s]))
                credits[s] -= 1.0
            except StopIteration:
                del iterators[s]

    return interleaved[:limit], total_counts
