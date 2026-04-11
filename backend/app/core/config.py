"""BooruHub backend configuration."""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://booruadmin:boorupass2024@db:5432/booruhub"

    # JWT
    JWT_SECRET: str = "change-me-to-a-random-secret-string-at-least-32-chars"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 10080  # 7 days

    # Encryption (for API keys stored in DB)
    ENCRYPTION_KEY: str = ""  # 32-byte base64 Fernet key; auto-derived from JWT_SECRET if empty

    # CORS
    CORS_ORIGINS: str = "*"  # comma-separated origins, or "*" for dev

    # Booru API keys (global fallback, per-user keys take priority)
    DANBOORU_LOGIN: str = ""
    DANBOORU_API_KEY: str = ""
    E621_LOGIN: str = ""
    E621_API_KEY: str = ""
    RULE34_API_KEY: str = ""
    RULE34_USER_ID: str = ""

    # Tag aliases file
    TAG_ALIASES_PATH: str = "/app/tag_aliases.csv"

    @property
    def cors_origin_list(self) -> list[str]:
        if self.CORS_ORIGINS.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
