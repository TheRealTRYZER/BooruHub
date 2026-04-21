"""Tests for the security module — encryption, passwords, and JWT tokens."""
import pytest
from app.core.security import (
    encrypt_key,
    decrypt_key,
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    create_refresh_token,
    decode_refresh_token,
)


class TestEncryption:
    def test_encrypt_decrypt_roundtrip(self):
        """it should encrypt and decrypt back to the original value"""
        original = "my_secret_api_key_12345"
        encrypted = encrypt_key(original)
        assert encrypted != original
        assert decrypt_key(encrypted) == original

    def test_encrypt_empty_string(self):
        """it should return empty string for empty input"""
        assert encrypt_key("") == ""
        assert decrypt_key("") == ""

    def test_decrypt_invalid_token(self):
        """it should return empty string for invalid encrypted data"""
        assert decrypt_key("not_a_valid_fernet_token") == ""

    def test_different_inputs_produce_different_ciphertexts(self):
        """it should produce different ciphertexts for different inputs"""
        a = encrypt_key("key_alpha")
        b = encrypt_key("key_beta")
        assert a != b


class TestPasswords:
    def test_hash_and_verify(self):
        """it should hash a password and verify it correctly"""
        password = "secure_password_123"
        hashed = hash_password(password)
        assert hashed != password
        assert verify_password(password, hashed)

    def test_wrong_password_fails(self):
        """it should reject an incorrect password"""
        hashed = hash_password("correct_password")
        assert not verify_password("wrong_password", hashed)

    def test_different_hashes_for_same_password(self):
        """it should produce different hashes due to random salt"""
        h1 = hash_password("same_password")
        h2 = hash_password("same_password")
        assert h1 != h2


class TestJWT:
    def test_create_and_decode_access_token(self):
        """it should create a valid access token that decodes correctly"""
        data = {"sub": "42"}
        token = create_access_token(data)
        payload = decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == "42"
        assert payload.get("type") == "access"

    def test_decode_invalid_token(self):
        """it should return None for an invalid token"""
        assert decode_access_token("invalid.token.here") is None

    def test_refresh_token_rejected_as_access(self):
        """it should reject a refresh token when decoded as access"""
        refresh = create_refresh_token({"sub": "42"})
        assert decode_access_token(refresh) is None

    def test_create_and_decode_refresh_token(self):
        """it should create a valid refresh token that decodes correctly"""
        data = {"sub": "99"}
        token = create_refresh_token(data)
        payload = decode_refresh_token(token)
        assert payload is not None
        assert payload["sub"] == "99"
        assert payload["type"] == "refresh"

    def test_access_token_rejected_as_refresh(self):
        """it should reject an access token when decoded as refresh"""
        access = create_access_token({"sub": "42"})
        assert decode_refresh_token(access) is None

    def test_decode_expired_refresh_token(self):
        """it should return None for a garbage refresh token"""
        assert decode_refresh_token("expired.garbage.token") is None
