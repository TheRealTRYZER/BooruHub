from app.core.config import Settings

def test_cookie_secure_defaults():
    # In development, it should default to False
    settings = Settings(ENVIRONMENT="development")
    assert settings.COOKIE_SECURE is False

    # In production, it should default to True
    settings = Settings(ENVIRONMENT="production")
    assert settings.COOKIE_SECURE is True

    # Explicit override to True should be preserved
    settings = Settings(ENVIRONMENT="development", COOKIE_SECURE=True)
    assert settings.COOKIE_SECURE is True

    # Explicit override to False should be preserved
    settings = Settings(ENVIRONMENT="production", COOKIE_SECURE=False)
    assert settings.COOKIE_SECURE is False


def test_api_docs_defaults_and_override():
    # Docs are enabled only in development by default
    assert Settings(ENVIRONMENT="development").ENABLE_API_DOCS is True
    assert Settings(ENVIRONMENT="production").ENABLE_API_DOCS is False

    # Explicit override wins regardless of environment
    assert Settings(ENVIRONMENT="production", ENABLE_API_DOCS=True).ENABLE_API_DOCS is True
    assert Settings(ENVIRONMENT="development", ENABLE_API_DOCS=False).ENABLE_API_DOCS is False
