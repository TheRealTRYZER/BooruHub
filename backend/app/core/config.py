"""BooruHub backend configuration."""
import ipaddress
from functools import lru_cache
from typing import Union

from pydantic import computed_field, model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    # COOKIE_SECURE defaults to True outside development. Deployments served over
    # plain HTTP (e.g. an IP address without TLS) MUST set COOKIE_SECURE=false,
    # otherwise browsers silently drop the auth cookies and login appears broken.
    COOKIE_SECURE: bool | None = None
    COOKIE_SAMESITE: str = "lax"
    # API docs are decoupled from ENVIRONMENT: they default to enabled only in
    # development, but can be forced on/off explicitly for any environment.
    ENABLE_API_DOCS: bool | None = None

    @model_validator(mode="after")
    def resolve_cookie_secure(self) -> "Settings":
        if self.COOKIE_SECURE is None:
            self.COOKIE_SECURE = self.ENVIRONMENT.lower() != "development"
        if self.ENABLE_API_DOCS is None:
            self.ENABLE_API_DOCS = self.ENVIRONMENT.lower() == "development"
        return self


    # Database
    DATABASE_URL: str = ""

    # JWT
    JWT_SECRET: str = ""
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 15  # 15 minutes
    # When a refresh token is rotated, the previous one is revoked. A second
    # request carrying the same (now revoked) token is normally a replay
    # attempt and revokes every session. Browsers legitimately produce that
    # race when two tabs refresh at once, so reuse is tolerated for this many
    # seconds after the rotation before it is treated as an attack.
    REFRESH_REUSE_GRACE_SECONDS: int = 30

    # CSRF protection is always on in production. The hostname check below is a
    # test-only escape hatch (see tests/conftest.py) and stays disabled unless
    # explicitly configured.
    CSRF_BYPASS_HOSTNAME: str = ""

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

    @computed_field  # type: ignore[prop-decorator]
    def trusted_proxy_networks(self) -> list[Union[ipaddress.IPv4Network, ipaddress.IPv6Network]]:
        """TRUSTED_PROXY_IPS entries that are CIDR blocks rather than single IPs."""
        networks = []
        for entry in self.trusted_proxy_ip_list:
            if "/" not in entry:
                continue
            try:
                networks.append(ipaddress.ip_network(entry, strict=False))
            except ValueError:
                continue
        return networks

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT.lower() == "development"

    class Config:
        env_file = [".env", "../.env"]
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
