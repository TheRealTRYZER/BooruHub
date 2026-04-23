"""BooruHub backend configuration."""
from functools import lru_cache

from pydantic import computed_field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    ENVIRONMENT: str = "development"

    # Database
    DATABASE_URL: str = ""

    # JWT
    JWT_SECRET: str = ""
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 10080  # 7 days

    # Encryption (for API keys stored in DB)
    ENCRYPTION_KEY: str = ""
    ENCRYPTION_KEY_FALLBACKS: str = ""

    # CORS
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8080,http://127.0.0.1:8080"

    # Booru API keys (global fallback, per-user keys take priority)
    DANBOORU_LOGIN: str = ""
    DANBOORU_API_KEY: str = ""
    E621_LOGIN: str = ""
    E621_API_KEY: str = ""
    RULE34_API_KEY: str = ""
    RULE34_USER_ID: str = ""

    # Tag aliases file
    TAG_ALIASES_PATH: str = "/app/tag_aliases.csv"

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

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT.lower() == "development"

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
