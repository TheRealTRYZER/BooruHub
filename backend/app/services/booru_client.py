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
    """Thread-safe bounded LRU cache with TTL using asyncio.Lock."""

    __slots__ = ("_data", "_max", "_lock")

    def __init__(self, maxsize: int = _CACHE_MAX) -> None:
        self._data: OrderedDict[tuple, tuple] = OrderedDict()
        self._max = maxsize
        self._lock: Optional[asyncio.Lock] = None

    async def get(self, key: tuple) -> Optional[tuple]:
        if self._lock is None:
            self._lock = asyncio.Lock()
        async with self._lock:
            entry = self._data.get(key)
            if entry is None:
                return None
            value, expiry = entry
            if time.monotonic() > expiry:
                self._data.pop(key, None)
                return None
            self._data.move_to_end(key)
            return value

    async def put(self, key: tuple, value: tuple) -> None:
        if not value:
            return
        if self._lock is None:
            self._lock = asyncio.Lock()
        async with self._lock:
            self._data[key] = (value, time.monotonic() + _CACHE_TTL)
            self._data.move_to_end(key)
            while len(self._data) > self._max:
                self._data.popitem(last=False)


_cache = _LRUCache()

# --------------------------------------------------------------------------- #
#  Per-user/per-site pacing                                                   #
# --------------------------------------------------------------------------- #

class TrackedLock(asyncio.Lock):
    def __init__(self) -> None:
        super().__init__()
        self.last_used = time.monotonic()
        self.in_use_count = 0

    async def __aenter__(self) -> None:
        self.in_use_count += 1
        self.last_used = time.monotonic()
        await super().__aenter__()

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        try:
            await super().__aexit__(exc_type, exc_val, exc_tb)
        finally:
            self.in_use_count -= 1
            self.last_used = time.monotonic()


_MAX_LOCKS = 256
_user_locks: Dict[tuple, TrackedLock] = {}
_last_search: Dict[tuple, float] = {}


def _get_lock(key: tuple) -> TrackedLock:
    """Get or create a lock for the given (user_id, site) key, with bounded size."""
    if key not in _user_locks:
        if len(_user_locks) >= _MAX_LOCKS:
            # Find candidate locks that are not in use/held
            candidates = [
                (k, l) for k, l in _user_locks.items()
                if l.in_use_count == 0 and not l.locked()
            ]
            if candidates:
                oldest_key, _ = min(candidates, key=lambda item: item[1].last_used)
                del _user_locks[oldest_key]
                _last_search.pop(oldest_key, None)
        _user_locks[key] = TrackedLock()
    else:
        _user_locks[key].last_used = time.monotonic()
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

    # Resolve adaptive timeout (use user setting or a highly responsive 10s default for guests)
    if timeout == 30.0:
        if user and getattr(user, "search_timeout", None):
            timeout = user.search_timeout
        else:
            timeout = 10.0

    # Cache lookup (B-L7: include timeout in cache key)
    cache_key = (site, tags, limit, page, timeout, user.id if user else None)
    cached = await _cache.get(cache_key)
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
    await _cache.put(cache_key, result)
    logger.debug(f"[{site}] {len(posts)} posts (tags='{tags}' page={page})")
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
) -> Tuple[List[dict], Dict[str, int], bool]:
    """Search multiple sites in parallel and interleave results by ratio weights.
    Returns (interleaved_posts, dict_of_unfiltered_counts_per_site, has_more).
    """
    sites = [s for s in site_queries if s in PROVIDERS and site_queries[s] is not None]
    if not sites:
        return [], {}, False

    # Determine per-site fetch limits
    num = len(sites)
    tasks = []
    site_limits = {}
    for site in sites:
        if num == 1:
            per_site = limit
        elif ratios and site in ratios:
            total_ratio = sum(ratios.values()) or 1.0
            share = ratios[site] / total_ratio
            if share >= 0.99:
                per_site = limit
            else:
                per_site = max(20, int(limit * 1.5 * share))
        else:
            per_site = max(20, int(limit * 1.2) // num)

        # Boost limit for Danbooru if it's likely searching with many tags (local filtering)
        # to ensure it contributes enough posts after filtering to interleave well.
        if site == "danbooru" and site_queries[site]:
            tag_count = len(site_queries[site].split())
            if tag_count > 2:
                per_site *= 4 # Fetch 4x more to account for local filter drop-off
        
        # Cap at the provider's max_per_page so the has_more heuristic
        # (total_counts >= site_limits) stays truthful — fetch_posts can never
        # return more raw posts than max_per_page, so an uncapped site_limit
        # would make has_more permanently false and stop pagination early.
        max_per_page = PROVIDERS[site].max_per_page
        per_site = min(per_site, max_per_page)
        
        site_limits[site] = per_site
        tasks.append(
            search_posts(
                site, site_queries[site], per_site, page,
                user=user, skip_interval=skip_interval,
            )
        )

    results = await asyncio.gather(*tasks, return_exceptions=True)

    by_site: Dict[str, List[dict]] = {}
    total_counts: Dict[str, int] = {}
    
    logger.debug(f"[MIX] Fetch results for page {page}:")
    for i, site in enumerate(sites):
        res = results[i]
        if isinstance(res, tuple) and len(res) == 2:
            posts, count = res
            by_site[site] = posts
            total_counts[site] = count
            logger.debug(f"    - {site}: {len(posts)} posts (matches: {count})")
        else:
            logger.error(f"    - {site}: Error: {res}")
            by_site[site] = []
            total_counts[site] = 0

    # Weighted interleaving algorithm with MD5 deduplication
    actual_ratios = ratios or {s: 1.0 for s in sites}
    credits = {s: 0.0 for s in sites}
    iterators = {s: iter(posts) for s, posts in by_site.items() if posts}
    interleaved: List[dict] = []
    # Interleaving loop
    while iterators:
        added_this_round = False
        # Give credits to all active iterators
        for s in list(iterators):
            credits[s] += actual_ratios.get(s, 1.0)

        # Sort eligible sites by credits (desc) to pull fairly. 
        # Stable tie-break by site order in the list.
        eligible = sorted(
            (s for s in iterators if credits[s] >= 1.0),
            key=lambda s: (credits[s], -sites.index(s)), 
            reverse=True,
        )
        
        if not eligible:
            # All ratios might be < 1.0; decrement 1.0 threshold if necessary or just bail
            break

        for s in eligible:
            try:
                post = next(iterators[s])
                interleaved.append(post)
                credits[s] -= 1.0
                added_this_round = True
            except StopIteration:
                del iterators[s]
                credits[s] = 0.0
        
        if not added_this_round:
            break

    logger.debug(f"[MIX] Interleaved {len(interleaved)} posts total")
    
    # Truthful has_more calculation
    has_more = False
    if len(interleaved) > limit:
        has_more = True
    else:
        for site in sites:
            # If a site returned at least site_limits[site] raw posts, it has remaining pages
            if total_counts.get(site, 0) >= site_limits.get(site, 1):
                has_more = True
                break

    truncated_posts = interleaved[:limit]
    return truncated_posts, total_counts, has_more
