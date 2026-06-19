import pytest
from unittest.mock import patch, MagicMock
from pydantic import ValidationError
from datetime import datetime, timezone, timedelta

from app.api.auth import RegisterRequest
from app.db.models import RefreshToken, User
from app.core.security import hash_refresh_token


def test_register_request_username_validation():
    # Valid
    req = RegisterRequest(username="valid_user-123", email="test@example.com", password="password123")
    assert req.username == "valid_user-123"
    assert req.data_consent is False  # Defaults to False

    # Invalid special char
    with pytest.raises(ValidationError):
        RegisterRequest(username="invalid@user", email="test@example.com", password="password123")

    # Invalid space
    with pytest.raises(ValidationError):
        RegisterRequest(username="invalid user", email="test@example.com", password="password123")


@pytest.mark.asyncio
async def test_register_endpoint_saves_refresh_token(client, mock_db):
    # 1. Check existing user (None)
    mock_existing = MagicMock()
    mock_existing.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_existing

    # Mock db.refresh to assign attributes since it's normally handled by DB autofill/refresh
    def mock_refresh(obj):
        obj.id = 1
        obj.default_tags = ""
    mock_db.refresh.side_effect = mock_refresh

    payload = {
        "username": "newuser",
        "email": "newuser@example.com",
        "password": "password123",
        "data_consent": True
    }
    
    response = await client.post("/api/auth/register", json=payload)
    assert response.status_code == 201
    
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["user"]["username"] == "newuser"

    # Verify that db.add was called for RefreshToken
    added_objs = [call.args[0] for call in mock_db.add.call_args_list]
    refresh_tokens = [obj for obj in added_objs if isinstance(obj, RefreshToken)]
    assert len(refresh_tokens) == 1
    assert refresh_tokens[0].token_hash == hash_refresh_token(data["refresh_token"])


@pytest.mark.asyncio
async def test_login_endpoint_saves_refresh_token(client, mock_db):
    user = User(id=1, username="testuser", email="test@example.com", default_tags="", password_hash="$2b$12$somehashedpassword")
    
    # 1. User query (return user)
    mock_user_query = MagicMock()
    mock_user_query.scalar_one_or_none.return_value = user

    # 2. Reload user during commit (return user)
    mock_reload = MagicMock()
    mock_reload.scalar_one_or_none.return_value = user

    mock_db.execute.side_effect = [mock_user_query, mock_reload]

    with patch("app.api.auth.verify_password", return_value=True):
        payload = {
            "login": "testuser",
            "password": "password123"
        }
        response = await client.post("/api/auth/login", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

        added_objs = [call.args[0] for call in mock_db.add.call_args_list]
        refresh_tokens = [obj for obj in added_objs if isinstance(obj, RefreshToken)]
        assert len(refresh_tokens) == 1
        assert refresh_tokens[0].token_hash == hash_refresh_token(data["refresh_token"])


@pytest.mark.asyncio
async def test_logout_endpoint_revokes_token(client, mock_db):
    refresh_token_record = RefreshToken(
        id=1,
        user_id=1,
        token_hash=hash_refresh_token("some_refresh_token"),
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        revoked=False
    )
    mock_db.execute.return_value.scalar_one_or_none.return_value = refresh_token_record

    payload = {"refresh_token": "some_refresh_token"}
    response = await client.post("/api/auth/logout", json=payload)
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert refresh_token_record.revoked is True


@pytest.mark.asyncio
async def test_refresh_token_endpoint_success(client, mock_db):
    refresh_token_record = RefreshToken(
        id=1,
        user_id=42,
        token_hash=hash_refresh_token("some_refresh_token"),
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        revoked=False
    )
    user = User(id=42, username="testuser", email="test@example.com", default_tags="")

    # Mock decode to return the subject id
    with patch("app.api.auth.decode_refresh_token", return_value={"sub": "42"}):
        # 1. Query for RefreshToken (return record)
        mock_token_query = MagicMock()
        mock_token_query.scalar_one_or_none.return_value = refresh_token_record

        # 2. Query for User (return user)
        mock_user_query = MagicMock()
        mock_user_query.scalar_one_or_none.return_value = user

        # 3. Query for cleanup (return arbitrary mock)
        mock_cleanup_query = MagicMock()

        mock_db.execute.side_effect = [mock_token_query, mock_user_query, mock_cleanup_query]

        payload = {"refresh_token": "some_refresh_token"}
        response = await client.post("/api/auth/refresh", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert refresh_token_record.revoked is True


@pytest.mark.asyncio
async def test_refresh_token_endpoint_invalid_or_expired(client, mock_db):
    # Case 1: Token not found
    with patch("app.api.auth.decode_refresh_token", return_value={"sub": "42"}):
        mock_token_query = MagicMock()
        mock_token_query.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_token_query

        payload = {"refresh_token": "invalid_token"}
        response = await client.post("/api/auth/refresh", json=payload)
        assert response.status_code == 401

    # Case 2: Token expired
    refresh_token_record = RefreshToken(
        id=1,
        user_id=42,
        token_hash=hash_refresh_token("expired_token"),
        expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        revoked=False
    )
    with patch("app.api.auth.decode_refresh_token", return_value={"sub": "42"}):
        mock_token_query = MagicMock()
        mock_token_query.scalar_one_or_none.return_value = refresh_token_record
        mock_db.execute.return_value = mock_token_query

        payload = {"refresh_token": "expired_token"}
        response = await client.post("/api/auth/refresh", json=payload)
        assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token_endpoint_replay_revokes_family(client, mock_db):
    refresh_token_record = RefreshToken(
        id=1,
        user_id=42,
        token_hash=hash_refresh_token("revoked_token"),
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        revoked=True
    )

    with patch("app.api.auth.decode_refresh_token", return_value={"sub": "42"}):
        mock_token_query = MagicMock()
        mock_token_query.scalar_one_or_none.return_value = refresh_token_record
        mock_db.execute.return_value = mock_token_query

        payload = {"refresh_token": "revoked_token"}
        response = await client.post("/api/auth/refresh", json=payload)
        assert response.status_code == 401

        # Check that update was executed to revoke all refresh tokens for this user
        execute_calls = mock_db.execute.call_args_list
        assert len(execute_calls) >= 2  # The select + the update
        
        # Check that update SQL expression was called
        update_call = execute_calls[1]
        sql_expr = update_call.args[0]
        # Assert it's an update object Targeting RefreshToken
        assert str(sql_expr).startswith("UPDATE refresh_tokens SET")
