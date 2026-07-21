"""BooruHub backend configuration."""
from functools import lru_cache

from pydantic import computed_field, model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    COOKIE_SECURE: bool | None = None
    COOKIE_SAMESITE: str = "lax"

    @model_validator(mode="after")
    def resolve_cookie_secure(self) -> "Settings":
        if self.COOKIE_SECURE is None:
            self.COOKIE_SECURE = self.ENVIRONMENT.lower() != "development"
        return self


    # Database
    DATABASE_URL: str = ""

    # JWT
    JWT_SECRET: str = ""
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 15  # 15 minutes

    # Encryption (for API keys stored in DB)
    ENCRYPTION_KEY: str = ""
    ENCRYPTION_KEY_FALLBACKS: str = ""

    # CORS
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8080,http://127.0.0.1:8080"
    TRUSTED_PROXY_IPS: str = "127.0.0.1,::1"

    # Booru API keys (global fallback, per-user keys take priority)
    DANBOORU_LOGIN: str = ""
    DANBOORU_API_KEY: str = ""
    E621_LOGIN: str = ""
    E621_API_KEY: str = ""
    RULE34_API_KEY: str = ""
    RULE34_USER_ID: str = ""
    enable_remote_autocomplete: bool = True


    @computed_field  # type: ignore[prop-decorator]
    def cors_origin_list(self) -> list[str]:
        if self.CORS_ORIGINS.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @computed_field  # type: ignore[prop-decorator]
    def encryption_key_fallback_list(self) -> list[str]:
        return [
            key.strip()
            for key in self.ENCRYPTION_KEY_FALLBACKS.split(",")
            if key.strip()
        ]

    @computed_field  # type: ignore[prop-decorator]
    def trusted_proxy_ip_list(self) -> list[str]:
        return [
            ip.strip()
            for ip in self.TRUSTED_PROXY_IPS.split(",")
            if ip.strip()
        ]

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT.lower() == "development"

    class Config:
        env_file = [".env", "../.env"]
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
