import pytest
import asyncio
import time
from unittest.mock import patch
from app.services.booru_client import _LRUCache

@pytest.mark.asyncio
async def test_lru_cache_basic_get_put():
    """it should store and retrieve items, respecting TTL"""
    cache = _LRUCache(maxsize=3)
    
    await cache.put(("site", "tags"), ("posts", 10))
    val = await cache.get(("site", "tags"))
    assert val == ("posts", 10)

@pytest.mark.asyncio
async def test_lru_cache_ttl_expiry():
    """it should evict expired items"""
    cache = _LRUCache(maxsize=3)
    
    with patch("time.monotonic", return_value=100.0):
        await cache.put(("key1",), ("val1",))
        
    with patch("time.monotonic", return_value=100.0 + 301.0): # past TTL of 300s
        val = await cache.get(("key1",))
        assert val is None

@pytest.mark.asyncio
async def test_lru_cache_eviction():
    """it should evict least recently used items when maxsize is exceeded"""
    cache = _LRUCache(maxsize=2)
    
    await cache.put(("k1",), ("v1",))
    await cache.put(("k2",), ("v2",))
    await cache.put(("k3",), ("v3",))
    
    assert await cache.get(("k1",)) is None
    assert await cache.get(("k2",)) == ("v2",)
    assert await cache.get(("k3",)) == ("v3",)

@pytest.mark.asyncio
async def test_lru_cache_concurrency():
    """it should handle concurrent operations safely using the lock"""
    cache = _LRUCache(maxsize=25)
    
    async def put_item(i):
        await cache.put((f"k{i}",), (f"v{i}",))
        await asyncio.sleep(0.01)
        val = await cache.get((f"k{i}",))
        assert val == (f"v{i}",)

    # Run many concurrent writes and reads
    await asyncio.gather(*(put_item(i) for i in range(20)))
