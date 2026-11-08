from app.core.config import Settings

def test_cookie_secure_defaults(monkeypatch):
    # Hermetic: ignore COOKIE_SECURE / ENVIRONMENT from a developer's local .env or shell.
    for k in ("COOKIE_SECURE", "ENVIRONMENT"):
        monkeypatch.delenv(k, raising=False)
    # In development, it should default to False
    settings = Settings(_env_file=None, ENVIRONMENT="development")
    assert settings.COOKIE_SECURE is False

    # In production, it should default to True
    settings = Settings(_env_file=None, ENVIRONMENT="production")
    assert settings.COOKIE_SECURE is True

    # Explicit override to True should be preserved
    settings = Settings(_env_file=None, ENVIRONMENT="development", COOKIE_SECURE=True)
    assert settings.COOKIE_SECURE is True

    # Explicit override to False should be preserved
    settings = Settings(_env_file=None, ENVIRONMENT="production", COOKIE_SECURE=False)
    assert settings.COOKIE_SECURE is False


def test_api_docs_defaults_and_override(monkeypatch):
    for k in ("ENABLE_API_DOCS", "ENVIRONMENT"):
        monkeypatch.delenv(k, raising=False)
    # Docs are enabled only in development by default
    assert Settings(_env_file=None, ENVIRONMENT="development").ENABLE_API_DOCS is True
    assert Settings(_env_file=None, ENVIRONMENT="production").ENABLE_API_DOCS is False

    # Explicit override wins regardless of environment
    assert Settings(_env_file=None, ENVIRONMENT="production", ENABLE_API_DOCS=True).ENABLE_API_DOCS is True
    assert Settings(_env_file=None, ENVIRONMENT="development", ENABLE_API_DOCS=False).ENABLE_API_DOCS is False
