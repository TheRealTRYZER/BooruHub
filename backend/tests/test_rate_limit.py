"""Tests for the rate limiter."""
import pytest
import asyncio
from app.core.rate_limit import _SlidingWindow


class TestSlidingWindow:
    @pytest.fixture
    def window(self):
        return _SlidingWindow(max_keys=100)

    async def test_allows_within_limit(self, window):
        """it should allow requests within the rate limit"""
        for _ in range(5):
            assert await window.check("user1", 5, 60)

    async def test_blocks_over_limit(self, window):
        """it should block requests exceeding the rate limit"""
        for _ in range(3):
            assert await window.check("user1", 3, 60)
        assert not await window.check("user1", 3, 60)

    async def test_different_keys_independent(self, window):
        """it should track different keys independently"""
        for _ in range(3):
            await window.check("user1", 3, 60)
        # user2 should still be allowed
        assert await window.check("user2", 3, 60)

    async def test_window_expiry(self, window):
        """it should allow requests after the window expires"""
        # Fill up the limit with a very short window
        for _ in range(2):
            assert await window.check("user1", 2, 0)  # 0-second window = immediate expiry
        # Should be allowed since old entries expired
        assert await window.check("user1", 2, 0)
