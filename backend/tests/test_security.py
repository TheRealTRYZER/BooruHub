"""Tests for the security module: encryption, passwords, and JWT tokens."""
import importlib

import pytest

from app.core import config as config_module
from app.core import security as security_module


PRIMARY_ENCRYPTION_KEY = "kC9M-L1LFI7hL7s0f17NdxbYF9bBlt3F4iAfDdc0AGQ="
ROTATED_ENCRYPTION_KEY = "6B8byGz2Ue9n4CnJw6K-kV9fG2hh_3Q1vM6liVnr6wQ="


@pytest.fixture
def security(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "x" * 64)
    monkeypatch.setenv("ENCRYPTION_KEY", PRIMARY_ENCRYPTION_KEY)
    monkeypatch.delenv("ENCRYPTION_KEY_FALLBACKS", raising=False)
    config_module.get_settings.cache_clear()
    module = importlib.reload(security_module)
    yield module
    config_module.get_settings.cache_clear()
    importlib.reload(security_module)


class TestEncryption:
    def test_encrypt_decrypt_roundtrip(self, security):
        original = "my_secret_api_key_12345"
        encrypted = security.encrypt_key(original)
        assert encrypted != original
        assert security.decrypt_key(encrypted) == original

    def test_encrypt_empty_string(self, security):
        assert security.encrypt_key("") == ""
        assert security.decrypt_key("") == ""

    def test_decrypt_invalid_token(self, security):
        assert security.decrypt_key("not_a_valid_fernet_token") == ""

    def test_different_inputs_produce_different_ciphertexts(self, security):
        a = security.encrypt_key("key_alpha")
        b = security.encrypt_key("key_beta")
        assert a != b

    def test_decrypt_with_fallback_key(self, monkeypatch, security):
        original = "legacy_secret"
        encrypted = security.encrypt_key(original)

        monkeypatch.setenv("ENCRYPTION_KEY", ROTATED_ENCRYPTION_KEY)
        monkeypatch.setenv("ENCRYPTION_KEY_FALLBACKS", PRIMARY_ENCRYPTION_KEY)
        config_module.get_settings.cache_clear()
        rotated = importlib.reload(security_module)

        assert rotated.decrypt_key(encrypted) == original


class TestPasswords:
    def test_hash_and_verify(self, security):
        password = "secure_password_123"
        hashed = security.hash_password(password)
        assert hashed != password
        assert security.verify_password(password, hashed)

    def test_wrong_password_fails(self, security):
        hashed = security.hash_password("correct_password")
        assert not security.verify_password("wrong_password", hashed)

    def test_different_hashes_for_same_password(self, security):
        h1 = security.hash_password("same_password")
        h2 = security.hash_password("same_password")
        assert h1 != h2


class TestJWT:
    def test_create_and_decode_access_token(self, security):
        token = security.create_access_token({"sub": "42"})
        payload = security.decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == "42"
        assert payload.get("type") == "access"

    def test_decode_invalid_token(self, security):
        assert security.decode_access_token("invalid.token.here") is None

    def test_refresh_token_rejected_as_access(self, security):
        refresh = security.create_refresh_token({"sub": "42"})
        assert security.decode_access_token(refresh) is None

    def test_create_and_decode_refresh_token(self, security):
        token = security.create_refresh_token({"sub": "99"})
        payload = security.decode_refresh_token(token)
        assert payload is not None
        assert payload["sub"] == "99"
        assert payload["type"] == "refresh"

    def test_access_token_rejected_as_refresh(self, security):
        access = security.create_access_token({"sub": "42"})
        assert security.decode_refresh_token(access) is None

    def test_decode_expired_refresh_token(self, security):
        assert security.decode_refresh_token("expired.garbage.token") is None
