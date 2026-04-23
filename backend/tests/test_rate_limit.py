"""Tests for the rate limiter."""
import pytest
from starlette.requests import Request

from app.core.rate_limit import _SlidingWindow
from app.core import config as config_module
from app.core.rate_limit import _get_client_ip


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


def _make_request(client_ip: str, forwarded_for: str | None = None) -> Request:
    headers = []
    if forwarded_for is not None:
        headers.append((b"x-forwarded-for", forwarded_for.encode()))
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": headers,
        "client": (client_ip, 12345),
        "server": ("testserver", 80),
        "scheme": "http",
    }
    return Request(scope)


class TestClientIpResolution:
    def test_ignores_spoofed_forwarded_header_from_untrusted_client(self, monkeypatch):
        monkeypatch.setenv("TRUSTED_PROXY_IPS", "127.0.0.1")
        config_module.get_settings.cache_clear()
        request = _make_request("203.0.113.10", "198.51.100.77")
        assert _get_client_ip(request) == "203.0.113.10"
        config_module.get_settings.cache_clear()

    def test_uses_forwarded_header_from_trusted_proxy(self, monkeypatch):
        monkeypatch.setenv("TRUSTED_PROXY_IPS", "127.0.0.1,::1")
        config_module.get_settings.cache_clear()
        request = _make_request("127.0.0.1", "198.51.100.77, 127.0.0.1")
        assert _get_client_ip(request) == "198.51.100.77"
        config_module.get_settings.cache_clear()
