import pytest
from unittest.mock import patch, MagicMock
from app.main import _validate_security_settings


def test_validate_security_settings_cors_wildcard():
    # Set config settings to trigger CORS wildcard error
    mock_settings = MagicMock()
    mock_settings.DATABASE_URL = "postgresql://localhost/db"
    mock_settings.JWT_SECRET = "x" * 64
    mock_settings.ENCRYPTION_KEY = "kC9M-L1LFI7hL7s0f17NdxbYF9bBlt3F4iAfDdc0AGQ="
    mock_settings.CORS_ORIGINS = "*"
    mock_settings.cors_origin_list = ["*"]
    mock_settings.is_development = False

    with patch("app.main.settings", mock_settings):
        with pytest.raises(RuntimeError) as exc_info:
            _validate_security_settings()
        assert "CORS wildcard '*' is not allowed" in str(exc_info.value)


def test_validate_security_settings_cors_empty_production():
    mock_settings = MagicMock()
    mock_settings.DATABASE_URL = "postgresql://localhost/db"
    mock_settings.JWT_SECRET = "x" * 64
    mock_settings.ENCRYPTION_KEY = "kC9M-L1LFI7hL7s0f17NdxbYF9bBlt3F4iAfDdc0AGQ="
    mock_settings.CORS_ORIGINS = ""
    mock_settings.cors_origin_list = []
    mock_settings.is_development = False

    with patch("app.main.settings", mock_settings):
        with pytest.raises(RuntimeError) as exc_info:
            _validate_security_settings()
        assert "Explicit CORS origins must be specified in production" in str(exc_info.value)
