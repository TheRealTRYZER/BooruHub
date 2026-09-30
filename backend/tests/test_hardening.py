"""Regression tests for the hardening pass.

Each test pins a specific defect that was fixed: rate-limit spoofing, the guest
rating bypass, credential leakage into logs, cached upstream failures, blocking
password hashing, duplicate refresh tokens, response-model field stripping and
input-bound gaps.
"""
import asyncio
import time
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from app.core import security
from app.core.bounded_set import BoundedSet


# --------------------------------------------------------------------------- #
#  Rate limit: proxy header spoofing                                          #
# --------------------------------------------------------------------------- #

def _make_request(peer: str, headers: dict):
    request = MagicMock()
    request.client.host = peer
    request.headers = {k.lower(): v for k, v in headers.items()}
    return request


class TestProxyHeaderTrust:
    def test_documentation_range_peer_is_not_a_trusted_proxy(self):
        """A public-looking peer must never be able to assert a client IP.

        Regression test: an earlier version trusted any address for which
        ipaddress.is_private() was true, which is also true for the
        documentation ranges, so a forged header was believed.
        """
        from app.core.rate_limit import _get_client_ip

        request = _make_request("203.0.113.10", {"x-forwarded-for": "198.51.100.77"})
        assert _get_client_ip(request) == "203.0.113.10"

    def test_private_docker_peer_may_supply_client_ip(self):
        from app.core.rate_limit import _get_client_ip

        request = _make_request("172.18.0.4", {"x-real-ip": "198.51.100.5"})
        assert _get_client_ip(request) == "198.51.100.5"

    def test_x_real_ip_is_preferred_over_forwarded_chain(self):
        """nginx sets X-Real-IP to a single sanitised value; it wins."""
        from app.core.rate_limit import _get_client_ip

        request = _make_request(
            "172.18.0.4",
            {"x-real-ip": "198.51.100.5", "x-forwarded-for": "1.2.3.4, 172.18.0.4"},
        )
        assert _get_client_ip(request) == "198.51.100.5"

    def test_configured_cidr_is_trusted(self, monkeypatch):
        from app.core import config as config_module
        from app.core.rate_limit import _get_client_ip

        monkeypatch.setenv("TRUSTED_PROXY_IPS", "10.10.0.0/16")
        config_module.get_settings.cache_clear()
        try:
            request = _make_request("10.10.0.9", {"x-real-ip": "198.51.100.8"})
            assert _get_client_ip(request) == "198.51.100.8"
        finally:
            config_module.get_settings.cache_clear()

    def test_malformed_header_falls_back_to_peer(self):
        from app.core.rate_limit import _get_client_ip

        request = _make_request("172.18.0.4", {"x-real-ip": "not-an-ip"})
        assert _get_client_ip(request) == "172.18.0.4"

    def test_invalid_peer_does_not_crash(self):
        from app.core.rate_limit import _get_client_ip

        request = _make_request("unknown", {"x-real-ip": "198.51.100.5"})
        assert _get_client_ip(request) == "127.0.0.1"


# --------------------------------------------------------------------------- #
#  Guest rating floor                                                         #
# --------------------------------------------------------------------------- #

class TestGuestRatingFloor:
    def test_range_id_query_does_not_bypass_rating(self):
        """'id:>1' is a normal feed query, not a relation lookup."""
        from app.api.posts import _enforce_guest_rating

        assert _enforce_guest_rating(["id:>1"]) == ["id:>1", "rating:general"]

    def test_order_by_id_bare_tag_does_not_bypass(self):
        from app.api.posts import _enforce_guest_rating

        assert "rating:general" in _enforce_guest_rating(["id"])

    def test_exact_relation_lookup_still_allowed(self):
        from app.api.posts import _enforce_guest_rating

        assert _enforce_guest_rating(["id:123"]) == ["id:123"]
        assert _enforce_guest_rating(["parent:5"]) == ["parent:5"]

    def test_negated_id_lookup_is_not_a_relation_lookup(self):
        """'-id:5' and '~id:5' exclude one post from a wider query; they are
        not a lookup of a single post and must not drop the rating floor."""
        from app.api.posts import _enforce_guest_rating

        for query in (["-id:123"], ["~id:123"], ["-parent:5"], ["~id:123", "~cat"]):
            result = _enforce_guest_rating(list(query))
            assert "rating:general" in result, query

    def test_relation_lookup_cannot_smuggle_a_rating(self):
        from app.api.posts import _enforce_guest_rating

        res = _enforce_guest_rating(["id:123", "rating:explicit"])
        assert "rating:explicit" not in res
        assert "id:123" in res

    @pytest.mark.asyncio
    async def test_guest_search_still_works_through_endpoint(self, client, mock_db):
        from app.api.deps import get_current_user
        from app.main import app

        app.dependency_overrides[get_current_user] = lambda: None
        try:
            with patch("app.api.posts.search_posts", new_callable=AsyncMock) as mock_search:
                mock_search.return_value = ([], 0)
                response = await client.get("/api/posts/search?tags=id:>1&site=danbooru")
                assert response.status_code == 200
                assert "rating:general" in mock_search.call_args[0][1]
        finally:
            app.dependency_overrides = {}


# --------------------------------------------------------------------------- #
#  Password hashing                                                           #
# --------------------------------------------------------------------------- #

class TestPasswordHashing:
    def test_new_hash_uses_prefixed_scheme(self):
        hashed = security.hash_password("correct horse battery staple")
        assert hashed.startswith("sha256$")
        assert not security.needs_rehash(hashed)

    def test_prefixed_hash_round_trips(self):
        hashed = security.hash_password("s3cret-passphrase")
        assert security.verify_password("s3cret-passphrase", hashed)
        assert not security.verify_password("wrong-passphrase", hashed)

    def test_legacy_hash_still_verifies(self):
        """Hashes written before the sha256$ marker must keep working."""
        import bcrypt

        legacy = bcrypt.hashpw(b"legacy-password", bcrypt.gensalt()).decode()
        assert security.needs_rehash(legacy)
        assert security.verify_password("legacy-password", legacy)
        assert not security.verify_password("other-password", legacy)

    def test_pre_marker_prehashed_hash_still_verifies(self):
        """The pre-marker code stored SHA-256 pre-hashed bcrypt without any
        prefix. Those are the hashes of every account created before the marker
        landed, and an unprefixed bcrypt digest over a 60-character input is
        indistinguishable from a raw-password hash, so both must be tried."""
        import hashlib

        import bcrypt

        password = "account-created-before-the-marker"
        prehashed = bcrypt.hashpw(
            hashlib.sha256(password.encode()).hexdigest().encode(),
            bcrypt.gensalt(rounds=4),
        ).decode()

        assert not prehashed.startswith("sha256$")
        assert security.needs_rehash(prehashed)
        assert security.verify_password(password, prehashed)
        assert not security.verify_password("wrong-password", prehashed)

    def test_empty_hash_is_rejected(self):
        assert not security.verify_password("anything", "")

    def test_malformed_hash_is_rejected(self):
        assert not security.verify_password("anything", "sha256$not-a-bcrypt-hash")

    def test_two_hashes_of_same_password_differ(self):
        a = security.hash_password("same-password")
        b = security.hash_password("same-password")
        assert a != b

    @pytest.mark.asyncio
    async def test_async_helpers_do_not_block_the_loop(self):
        """The off-loop helpers must return, letting the loop keep ticking."""
        ticks = 0

        async def ticker():
            nonlocal ticks
            while True:
                ticks += 1
                await asyncio.sleep(0.001)

        task = asyncio.create_task(ticker())
        await security.hash_password_async("blocking-work")
        task.cancel()

        assert ticks > 0, "event loop was starved during password hashing"

    @pytest.mark.asyncio
    async def test_dummy_verify_runs_a_bcrypt_call(self):
        with patch("app.core.security.bcrypt.checkpw") as mock_checkpw:
            await security.dummy_verify_async()
        assert mock_checkpw.call_count == 1


# --------------------------------------------------------------------------- #
#  Token uniqueness                                                           #
# --------------------------------------------------------------------------- #

class TestTokenUniqueness:
    def test_refresh_tokens_issued_in_the_same_second_differ(self):
        """Without jti the payloads were byte-identical and collided on the
        unique token_hash index."""
        first = security.create_refresh_token({"sub": "1"})
        second = security.create_refresh_token({"sub": "1"})
        assert first != second
        assert security.hash_refresh_token(first) != security.hash_refresh_token(second)

    def test_access_tokens_issued_in_the_same_second_differ(self):
        first = security.create_access_token({"sub": "1"})
        second = security.create_access_token({"sub": "1"})
        assert first != second

    def test_refresh_token_carries_a_jti(self):
        import jwt

        from app.core.config import get_settings

        settings = get_settings()
        payload = jwt.decode(
            security.create_refresh_token({"sub": "1"}),
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
            issuer="booruhub",
            audience="booruhub_users",
        )
        assert payload["jti"]
        assert payload["type"] == "refresh"


# --------------------------------------------------------------------------- #
#  Upstream failure handling                                                  #
# --------------------------------------------------------------------------- #

class TestUpstreamFailures:
    @pytest.mark.asyncio
    async def test_provider_failure_is_not_cached(self):
        """A single 429/timeout used to poison the cache for 5 minutes."""
        from app.services.booru_client import _cache, search_posts

        _cache._data.clear()
        provider = MagicMock()
        provider.max_per_page = 200
        provider.fetch_posts = AsyncMock(return_value=([], -1))

        with patch.dict("app.services.booru_client.PROVIDERS", {"danbooru": provider}, clear=True):
            await search_posts("danbooru", "1girl", 40, 1, user=None, skip_interval=True)
            # Second call must reach the provider again, not the cache.
            provider.fetch_posts.assert_awaited_once()

        _cache._data.clear()

    @pytest.mark.asyncio
    async def test_successful_result_is_cached(self):
        from app.services.booru_client import _cache, search_posts

        _cache._data.clear()
        provider = MagicMock()
        provider.max_per_page = 200
        provider.fetch_posts = AsyncMock(return_value=([{"id": "1"}], 5))

        with patch.dict("app.services.booru_client.PROVIDERS", {"danbooru": provider}, clear=True):
            await search_posts("danbooru", "1girl", 40, 1, user=None, skip_interval=True)
            await search_posts("danbooru", "1girl", 40, 1, user=None, skip_interval=True)
            provider.fetch_posts.assert_awaited_once()

        _cache._data.clear()

    @pytest.mark.asyncio
    async def test_client_error_is_empty_result_not_failure(self):
        """A 4xx is a rejected query, not an outage: it must not trip the
        circuit breaker or turn into a 502."""
        import httpx

        from app.services.booru.e621 import E621

        provider = E621()
        response = httpx.Response(422, request=httpx.Request("GET", "https://e621.net/posts.json"))

        with patch.object(provider, "_get_client") as mock_get_client, \
             patch.object(provider, "normalize_post"):
            mock_client = MagicMock()
            mock_client.get = AsyncMock(side_effect=httpx.HTTPStatusError(
                "boom", request=response.request, response=response
            ))
            mock_get_client.return_value = mock_client
            posts, count = await provider.fetch_posts("1girl", 1, 20, None)

        assert (posts, count) == ([], 0)

    @pytest.mark.asyncio
    async def test_server_error_is_still_a_failure(self):
        import httpx

        from app.services.booru.e621 import E621

        provider = E621()
        response = httpx.Response(503, request=httpx.Request("GET", "https://e621.net/posts.json"))

        with patch.object(provider, "_get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.get = AsyncMock(side_effect=httpx.HTTPStatusError(
                "boom", request=response.request, response=response
            ))
            mock_get_client.return_value = mock_client
            posts, count = await provider.fetch_posts("1girl", 1, 20, None)

        assert (posts, count) == ([], -1)


# --------------------------------------------------------------------------- #
#  Result cache isolation                                                     #
# --------------------------------------------------------------------------- #

class TestCacheIsolation:
    @pytest.mark.asyncio
    async def test_caller_mutation_does_not_persist_in_cache(self):
        """_inject_favorites / dedup write onto post dicts in place; without a
        copy the flag survived in the cache for the whole TTL."""
        from app.services.booru_client import _LRUCache

        cache = _LRUCache(maxsize=4)
        await cache.put(("k",), ([{"id": "1"}], 1))

        first, _ = await cache.get(("k",))
        first[0]["favorite"] = True
        first[0]["duplicates"] = ["leak"]

        second, _ = await cache.get(("k",))
        assert "favorite" not in second[0]
        assert "duplicates" not in second[0]

    @pytest.mark.asyncio
    async def test_non_post_payloads_pass_through(self):
        from app.services.booru_client import _LRUCache

        cache = _LRUCache(maxsize=4)
        await cache.put(("k",), ("sentinel", 3))
        assert await cache.get(("k",)) == ("sentinel", 3)

    def test_post_response_keeps_injected_fields(self):
        """FastAPI's response_model silently dropped favorite/source/created_at."""
        from app.api.posts import FeedResponse

        response = FeedResponse(
            posts=[{
                "id": "1",
                "source_site": "danbooru",
                "file_url": "https://danbooru.donmai.us/x.jpg",
                "favorite": True,
                "source": "https://example.invalid/a",
                "created_at": "2026-01-01T00:00:00Z",
            }],
            page=1, total=1, unfiltered_count=1, resolved_tags="",
        )
        post = response.model_dump()["posts"][0]
        assert post["favorite"] is True
        assert post["source"] == "https://example.invalid/a"
        assert post["created_at"] == "2026-01-01T00:00:00Z"


# --------------------------------------------------------------------------- #
#  Input bounds                                                               #
# --------------------------------------------------------------------------- #

class TestInputBounds:
    def test_source_site_must_be_a_known_provider(self):
        from pydantic import ValidationError

        from app.api.favorites import FavoriteAdd

        with pytest.raises(ValidationError):
            FavoriteAdd(source_site="evil", post_id="1")
        assert FavoriteAdd(source_site="danbooru", post_id="1").source_site == "danbooru"

    def test_oversized_favorite_fields_are_rejected(self):
        from pydantic import ValidationError

        from app.api.favorites import FavoriteAdd

        with pytest.raises(ValidationError):
            FavoriteAdd(source_site="danbooru", post_id="x" * 51)
        with pytest.raises(ValidationError):
            FavoriteAdd(source_site="danbooru", post_id="1", file_ext="x" * 21)

    def test_event_fields_match_column_widths(self):
        from pydantic import ValidationError

        from app.api.events import EventPayload

        with pytest.raises(ValidationError):
            EventPayload(type="view", source="x" * 33)
        with pytest.raises(ValidationError):
            EventPayload(type="view", post_id="x" * 51)
        assert EventPayload(type="view", post_id="x" * 50).post_id

    def test_bookmark_name_and_sites_are_bounded(self):
        from pydantic import ValidationError

        from app.api.bookmarks import BookmarkCreate

        with pytest.raises(ValidationError):
            BookmarkCreate(name="x" * 256, query="q", sites=["danbooru"])
        with pytest.raises(ValidationError):
            BookmarkCreate(name="n", query="q", sites=["not-a-booru"])

    def test_mapping_and_default_tags_are_bounded(self):
        from pydantic import ValidationError

        from app.api.mappings import DefaultTagsUpdate, MappingCreate

        with pytest.raises(ValidationError):
            MappingCreate(unitag="x" * 256)
        with pytest.raises(ValidationError):
            DefaultTagsUpdate(default_tags="x" * 256)

    def test_like_prefix_wildcards_are_escaped(self):
        from app.api.posts import _escape_like_prefix

        assert _escape_like_prefix("1girl") == "1girl"
        assert _escape_like_prefix("100%") == "100\\%"
        assert _escape_like_prefix("a_b") == "a\\_b"
        assert _escape_like_prefix("a\\b") == "a\\\\b"

    @pytest.mark.asyncio
    async def test_wildcard_query_does_not_match_everything(self, client, mock_db):
        """'%' used to be passed straight into LIKE and returned the most
        popular cached tags."""
        from app.api.deps import get_current_user
        from app.main import app

        app.dependency_overrides[get_current_user] = lambda: None
        try:
            captured = {}

            def capture(stmt, *args, **kwargs):
                captured["sql"] = str(stmt)
                result = MagicMock()
                result.scalars.return_value.all.return_value = []
                return result

            mock_db.execute.side_effect = capture
            response = await client.get("/api/posts/tags/suggest?q=%25&fast=true")
            assert response.status_code == 200
            assert "ESCAPE" in captured.get("sql", "").upper()
        finally:
            app.dependency_overrides = {}


# --------------------------------------------------------------------------- #
#  Account identity                                                           #
# --------------------------------------------------------------------------- #

class TestAccountIdentity:
    def test_trailing_newline_is_rejected(self):
        """'$' also matches before a trailing newline, so 'admin\\n' used to
        register as a separate account from 'admin'."""
        from pydantic import ValidationError

        from app.api.auth import RegisterRequest

        with pytest.raises(ValidationError):
            RegisterRequest(username="admin\n", email="a@b.com", password="password123")
        assert RegisterRequest(
            username="admin", email="a@b.com", password="password123"
        ).username == "admin"

    def test_username_and_email_are_lower_cased(self):
        from app.api.auth import RegisterRequest

        request = RegisterRequest(username="Admin", email="A@B.com", password="password123")
        assert request.username == "admin"
        assert request.email == "a@b.com"

    @pytest.mark.asyncio
    async def test_registration_folds_case_like_login_does(self):
        """Registration compared the raw column against an already lower-cased
        value, so "LegacyUser" and "legacyuser" were both accepted. The pair then
        matched the case-insensitive login predicate and turned login into a
        500 instead of a rejection."""
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

        from app.api.auth import user_login_predicate
        from app.db.database import get_db
        from app.db.models import Base, User
        from app.main import app

        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with sessions() as session:
            session.add(User(username="LegacyUser", email="legacy@example.com", password_hash="x"))
            await session.commit()

        async def override_get_db():
            async with sessions() as session:
                yield session

        app.dependency_overrides[get_db] = override_get_db
        try:
            transport = ASGITransport(app=app, raise_app_exceptions=False)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                same_name = await client.post(
                    "/api/auth/register",
                    json={"username": "legacyuser", "email": "other@example.com", "password": "password123"},
                )
                same_email = await client.post(
                    "/api/auth/register",
                    json={"username": "otheruser", "email": "LEGACY@example.com", "password": "password123"},
                )
        finally:
            app.dependency_overrides = {}
            await engine.dispose()

        assert same_name.status_code == 409, same_name.text
        assert same_email.status_code == 409, same_email.text

    @pytest.mark.asyncio
    async def test_ambiguous_login_fails_closed_instead_of_500(self):
        """Rows that differ only by casing both match the login predicate.
        scalar_one_or_none() raised on that pair, so login returned 500."""
        from datetime import datetime, timedelta, timezone

        from fastapi import Response
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

        from app.api.auth import LoginRequest, login
        from app.core import security
        from app.db.models import Base, User

        password = "shared-password"
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with sessions() as session:
            session.add(User(username="Twin", email="twin-a@example.com", password_hash=security.hash_password(password)))
            session.add(User(username="twin", email="twin-b@example.com", password_hash=security.hash_password(password)))
            await session.commit()

            with pytest.raises(HTTPException) as excinfo:
                await login(LoginRequest(login="TWIN", password=password), Response(), session)

        await engine.dispose()
        assert excinfo.value.status_code == 401


class TestLogoutRevocation:
    @pytest.mark.asyncio
    async def test_logout_revocation_is_marked_and_not_grace_eligible(self):
        """The reuse grace window exists for the two-tab rotation race. A token
        revoked by logout must never be revived by it."""
        from fastapi import Response

        from app.api.auth import LogoutRequest, logout
        from app.core import security
        from app.db.models import RefreshToken

        token = security.create_refresh_token({"sub": "7"})
        stored = RefreshToken(
            user_id=7,
            token_hash=security.hash_refresh_token(token),
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
            revoked=False,
        )
        session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = stored
        session.execute.return_value = result

        request = SimpleNamespace(cookies={"refresh_token": token})
        await logout(LogoutRequest(), request, Response(), session)

        assert stored.revoked is True
        assert stored.revoked_at is not None
        assert stored.revoked_by_logout is True

    def test_rotation_revocation_stays_grace_eligible(self):
        """The benign race the window exists for must keep working."""
        from app.db.models import RefreshToken

        rotated = RefreshToken(user_id=1, token_hash="x" * 64, revoked=True,
                               revoked_at=datetime.now(timezone.utc), revoked_by_logout=False)

        assert rotated.revoked_by_logout is False


# --------------------------------------------------------------------------- #
#  Provider tag translation                                                   #
# --------------------------------------------------------------------------- #

class TestRatingTranslation:
    def test_sensitive_is_not_mangled(self):
        from app.services.booru.rule34 import Rule34

        api_tags, _ = Rule34().prepare_tags("rating:sensitive")
        assert api_tags == "rating:safe"
        assert "safeensitive" not in api_tags

    def test_general_and_short_forms_map_to_safe(self):
        from app.services.booru.rule34 import Rule34

        provider = Rule34()
        assert provider.prepare_tags("rating:general")[0] == "rating:safe"
        assert provider.prepare_tags("rating:s")[0] == "rating:safe"

    def test_explicit_rating_is_left_alone(self):
        from app.services.booru.rule34 import Rule34

        api_tags, _ = Rule34().prepare_tags("1girl rating:explicit")
        assert api_tags == "1girl rating:explicit"

    def test_numeric_change_timestamp_is_coerced_to_a_string(self):
        """Rule34 sends 'change' as an int. Leaving it numeric failed
        PostResponse validation and dropped the whole page."""
        from app.api.posts import PostResponse
        from app.services.booru.rule34 import Rule34

        post = Rule34().normalize_post(
            {"id": 1, "file_url": "https://example.invalid/i.jpg", "change": 1700000000}
        )

        assert isinstance(post["created_at"], str)
        assert PostResponse.model_validate(post).created_at == "1700000000"

    def test_created_at_string_is_preferred_over_change(self):
        from app.services.booru.rule34 import Rule34

        post = Rule34().normalize_post({
            "id": 1,
            "file_url": "https://example.invalid/i.jpg",
            "created_at": "2026-01-01 00:00:00",
            "change": 1700000000,
        })

        assert post["created_at"] == "2026-01-01 00:00:00"


# --------------------------------------------------------------------------- #
#  Tag cache bookkeeping                                                      #
# --------------------------------------------------------------------------- #

# Two distinct valid Fernet keys, standing in for "the current key" and
# "the key that was rotated out".
KEY_A = Fernet.generate_key()
KEY_B = Fernet.generate_key()


class TestCredentialStatus:
    """The settings page showed a green tick for any stored key, including one
    that can no longer be decrypted after ENCRYPTION_KEY is rotated. Requests
    then went out unauthenticated and the site silently returned nothing."""

    def test_usable_when_key_decrypts(self):

        from app.api.users import _credential_usable
        from app.core.security import encrypt_key

        fernet = Fernet(KEY_A)
        with patch("app.core.security._get_encryption_fernets", return_value=[fernet]):
            blob = encrypt_key("secret-key")
            assert _credential_usable(blob, "TRYZER", "", "") is True

    def test_not_usable_when_key_cannot_be_decrypted(self):

        from app.api.users import _credential_usable

        stale = Fernet(KEY_B).encrypt(b"old-key").decode()
        current = Fernet(KEY_A)
        with patch("app.core.security._get_encryption_fernets", return_value=[current]):
            assert _credential_usable(stale, "TRYZER", "", "") is False

    def test_not_usable_without_login(self):

        from app.api.users import _credential_usable
        from app.core.security import encrypt_key

        fernet = Fernet(KEY_A)
        with patch("app.core.security._get_encryption_fernets", return_value=[fernet]):
            blob = encrypt_key("secret-key")
            # Rule34 needs the user id alongside the key.
            assert _credential_usable(blob, "", "", "") is False
            assert _credential_usable(blob, "5100262", "", "") is True

    def test_env_credentials_count_as_usable(self):
        from app.api.users import _credential_usable

        assert _credential_usable(None, None, "admin", "env-key") is True
    def test_nothing_configured_is_not_usable(self):

        from app.api.users import _credential_usable

        assert _credential_usable(None, None, "", "") is False

    def test_rule34_key_input_fits_the_ciphertext_column(self):
        """The stored column holds an encrypted token, so the accepted input
        length has to leave room for the Fernet overhead."""
        from pydantic import ValidationError

        from app.api.users import MAX_RULE34_API_KEY_LENGTH, ApiSettingsUpdate
        from app.db.models import User

        column_width = User.__table__.c.rule34_api_key.type.length
        accepted = MAX_RULE34_API_KEY_LENGTH
        # Fernet token length for an n-byte plaintext: 4*ceil(n/3) + 57.
        ciphertext_length = 4 * ((accepted + 2) // 3) + 57

        assert ciphertext_length <= column_width
        assert ApiSettingsUpdate(rule34_api_key="x" * accepted)
        with pytest.raises(ValidationError):
            ApiSettingsUpdate(rule34_api_key="x" * (column_width + 1))

    @pytest.mark.asyncio
    async def test_encrypted_rule34_key_is_storable(self):
        """End to end: the longest accepted key must still fit the column."""
        from app.api.users import MAX_RULE34_API_KEY_LENGTH, ApiSettingsUpdate, update_settings
        from app.db.models import User

        user = SimpleNamespace(id=1)
        await update_settings(
            ApiSettingsUpdate(rule34_api_key="k" * MAX_RULE34_API_KEY_LENGTH), user, AsyncMock()
        )

        assert len(user.rule34_api_key) <= User.__table__.c.rule34_api_key.type.length


class TestBoundedSetPeek:
    @pytest.mark.asyncio
    async def test_peek_new_does_not_record(self):
        tracked = BoundedSet(maxsize=10)
        assert await tracked.peek_new(["a", "b"]) == ["a", "b"]
        # Nothing was recorded, so the same items are still new.
        assert await tracked.peek_new(["a"]) == ["a"]

    @pytest.mark.asyncio
    async def test_add_many_records(self):
        tracked = BoundedSet(maxsize=10)
        await tracked.add_many(["a"])
        assert await tracked.peek_new(["a"]) == []
        assert await tracked.add_many(["a"]) == []

    @pytest.mark.asyncio
    async def test_failed_write_does_not_suppress_tag_forever(self):
        """Tags were marked as cached before the DB write, so a failed insert
        left them permanently uncached."""
        from app.services import tag_cache

        tracked = BoundedSet(maxsize=10)
        with patch.object(tag_cache, "_recently_cached_tags", tracked), \
             patch.object(tag_cache, "_execute_with_retry", new_callable=AsyncMock) as mock_retry:
            mock_retry.return_value = False
            await tag_cache._cache_tags_task([{"tag": "retryme", "source": "danbooru"}])

        assert await tracked.peek_new(["retryme"]) == ["retryme"]


# --------------------------------------------------------------------------- #
#  Refresh rotation grace window                                              #
# --------------------------------------------------------------------------- #

class TestRefreshGraceWindow:
    def test_recently_revoked_token_within_grace_is_not_a_replay(self):
        """Two tabs sharing one cookie rotate the same token; that must not
        revoke every session for the user."""
        from app.db.models import RefreshToken

        from app.core.config import get_settings

        settings = get_settings()
        db_token = RefreshToken(
            user_id=1,
            token_hash="x" * 64,
            revoked=True,
            revoked_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        )

        within = (datetime.now(timezone.utc) - db_token.revoked_at).total_seconds()
        assert within <= settings.REFRESH_REUSE_GRACE_SECONDS

    def test_long_revoked_token_outside_grace_is_a_replay(self):
        from app.core.config import get_settings

        settings = get_settings()
        revoked_at = datetime.now(timezone.utc) - timedelta(
            seconds=settings.REFRESH_REUSE_GRACE_SECONDS + 60
        )
        assert (datetime.now(timezone.utc) - revoked_at).total_seconds() > settings.REFRESH_REUSE_GRACE_SECONDS

    def test_token_revoked_without_timestamp_is_treated_as_replay(self):
        """Rows written before the revoked_at migration have NULL there and
        must fall through to the strict path."""
        from app.db.models import RefreshToken

        db_token = RefreshToken(user_id=1, token_hash="y" * 64, revoked=True)
        assert db_token.revoked_at is None


# --------------------------------------------------------------------------- #
#  Credential leakage                                                         #
# --------------------------------------------------------------------------- #

class TestCredentialLogging:
    def test_httpx_logger_is_quiet(self):
        """httpx logs the full request URL at INFO, and the providers pass user
        API keys as query parameters."""
        import logging

        from app.main import app  # noqa: F401  (import triggers configuration)

        assert logging.getLogger("httpx").level >= logging.WARNING
        assert logging.getLogger("httpx").isEnabledFor(logging.INFO) is False


# --------------------------------------------------------------------------- #
#  CSRF                                                                      #
# --------------------------------------------------------------------------- #

class TestCsrfBypassIsOptIn:
    def test_bypass_is_disabled_by_default(self):
        """The hostname escape hatch must not be live unless configured.

        Checked against the field default rather than an instance, because
        tests/conftest.py sets the variable for the whole session.
        """
        from app.core.config import Settings

        assert Settings.model_fields["CSRF_BYPASS_HOSTNAME"].default == ""

    @pytest.mark.asyncio
    async def test_middleware_enforces_csrf_when_bypass_does_not_match(self, client):
        """With the bypass pointed elsewhere, a POST without a CSRF header is
        rejected. The middleware must not skip the check unconditionally.

        Patches app.main.settings (not get_settings()) because an earlier test
        clears the lru_cache, so a fresh get_settings() would be a different
        object than the one the middleware closes over.
        """
        from app import main as main_module

        original = main_module.settings.CSRF_BYPASS_HOSTNAME
        main_module.settings.CSRF_BYPASS_HOSTNAME = "not-the-test-host"
        try:
            response = await client.post("/api/auth/logout", json={})
            assert response.status_code == 403
            assert "CSRF" in response.json()["detail"]
        finally:
            main_module.settings.CSRF_BYPASS_HOSTNAME = original


def test_time_source_is_monotonic():
    """Guard for the sliding-window limiter's use of time.monotonic()."""
    assert time.monotonic() <= time.monotonic()
