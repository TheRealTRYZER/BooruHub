"""Base class for all booru providers.

Provides:
- Shared httpx.AsyncClient with connection pooling (one per provider)
- Unified auth parameter resolution (user DB → global .env fallback)
- Configurable hooks: prepare_tags, calculate_page, handle_error_response
- Standard post normalisation contract via abstract normalize_post()
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple

import httpx
import logging

from app.core.security import decrypt_key
from app.core.config import get_settings
from app.db.models import User

logger = logging.getLogger(__name__)


class BaseBooru(ABC):
    """Abstract base for every imageboard provider."""

    def __init__(self) -> None:
        # Subclasses MUST set these in their __init__
        self.base_url: str = ""
        self.posts_path: str = ""
        self.max_per_page: int = 100
        self.page_param: str = "page"
        self.start_page: int = 1
        self.is_wrapped: bool = False          # True if JSON is {"posts": [...]}
        self.user_agent: str = "BooruHub/1.0"
        self.default_params: dict = {}

        # Pairs of (user_field_prefix, settings_field_prefix) for auth resolution
        # e.g. [("danbooru_login", "danbooru_api_key", "DANBOORU_LOGIN", "DANBOORU_API_KEY")]
        self.auth_fields: List[Tuple[str, str, str, str]] = []

        # Shared httpx client (lazy-initialised on first request)
        self._client: Optional[httpx.AsyncClient] = None

    # ------------------------------------------------------------------ #
    #  HTTP client (connection-pooled, reused across requests)            #
    # ------------------------------------------------------------------ #

    def _get_client(self, timeout: float = 30.0) -> httpx.AsyncClient:
        """Return a shared AsyncClient, creating it on first call."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                headers={"User-Agent": self.user_agent},
                timeout=httpx.Timeout(timeout, connect=10.0),
                follow_redirects=True,
                limits=httpx.Limits(
                    max_connections=20,
                    max_keepalive_connections=10,
                    keepalive_expiry=120,
                ),
            )
        return self._client

    # ------------------------------------------------------------------ #
    #  Auth helpers                                                       #
    # ------------------------------------------------------------------ #

    def _read_user_credential(self, user: User, field: str, encrypted: bool = False) -> str:
        """Safely read a credential from a User object."""
        val = getattr(user, field, None)
        if not val:
            return ""
        if encrypted:
            decrypted = decrypt_key(val)
            return decrypted.strip() if decrypted else ""
        return val.strip()

    def get_auth_params(self, user: Optional[User]) -> Dict[str, str]:
        """Resolve auth params: user credentials first, then global settings fallback.

        Subclasses should set self.auth_fields in __init__ to configure which
        DB/env fields to look up.  Format per entry:
            (user_login_field, user_key_field, settings_login_var, settings_key_var)
        """
        params: Dict[str, str] = {}
        if not self.auth_fields:
            return params

        for user_login_field, user_key_field, env_login_var, env_key_var in self.auth_fields:
            # Try user-level credentials first
            if user:
                login_val = self._read_user_credential(user, user_login_field)
                key_val = self._read_user_credential(user, user_key_field, encrypted=True)
                if login_val:
                    params[self._auth_param_name(user_login_field)] = login_val
                if key_val:
                    params[self._auth_param_name(user_key_field)] = key_val

            # Fallback to env if nothing found from user
            if not params:
                settings = get_settings()
                env_login = getattr(settings, env_login_var, "")
                env_key = getattr(settings, env_key_var, "")
                if env_login and env_login.strip():
                    params[self._auth_param_name(user_login_field)] = env_login.strip()
                if env_key and env_key.strip():
                    params[self._auth_param_name(user_key_field)] = env_key.strip()

        return params

    def _auth_param_name(self, field_name: str) -> str:
        """Convert DB field name to API query param name.
        e.g. 'danbooru_login' → 'login', 'rule34_user_id' → 'user_id'
        """
        # Strip the site prefix: 'danbooru_login' → 'login', 'rule34_api_key' → 'api_key'
        parts = field_name.split("_", 1)
        return parts[1] if len(parts) > 1 else field_name

    # ------------------------------------------------------------------ #
    #  Hooks (override in subclasses)                                     #
    # ------------------------------------------------------------------ #

    @abstractmethod
    def normalize_post(self, raw: dict) -> Optional[dict]:
        """Convert site-specific post JSON to unified BooruHub format."""
        ...

    def prepare_tags(self, tags: str) -> Tuple[str, List[str]]:
        """Apply site-specific tag transformations before querying.

        Returns:
            (api_tags, extra_tags): api_tags is sent to the remote API,
            extra_tags are filtered locally after the response.
        """
        return tags, []

    def calculate_page(self, page: int, limit: int) -> int:
        """Convert 1-based page number to site-specific index/offset."""
        return page

    async def handle_error_response(
        self,
        resp: httpx.Response,
        client: httpx.AsyncClient,
        url: str,
        params: dict,
        original_tags: str,
    ) -> httpx.Response:
        """Hook called when the API returns a non-200 status. Return a replacement
        response or the original to let the caller raise."""
        return resp

    # ------------------------------------------------------------------ #
    #  Core fetch logic                                                   #
    # ------------------------------------------------------------------ #

    async def fetch_posts(
        self,
        tags: str,
        page: int,
        limit: int,
        user: Optional[User],
        timeout: float = 30.0,
    ) -> Tuple[List[dict], int]:
        """Fetch posts from the remote API, normalise, and return."""
        actual_page = self.calculate_page(page, limit)
        api_tags, extra_tags = self.prepare_tags(tags)
        auth_params = self.get_auth_params(user)

        # Fetch more if local filtering is needed
        fetch_limit = limit * 3 if extra_tags else limit
        fetch_limit = min(fetch_limit, self.max_per_page)

        params = {
            **self.default_params,
            "tags": api_tags,
            "limit": fetch_limit,
            self.page_param: actual_page,
            **auth_params,
        }

        url = f"{self.base_url}{self.posts_path}"
        client = self._get_client(timeout)

        try:
            resp = await client.get(url, params=params)

            if resp.status_code != 200:
                resp = await self.handle_error_response(resp, client, url, params, tags)

            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as e:
            logger.warning(f"[{self.__class__.__name__}] HTTP {e.response.status_code} for tags='{tags}'")
            return [], 0
        except httpx.RequestError as e:
            logger.error(f"[{self.__class__.__name__}] Network error: {e}")
            return [], 0

        # Unwrap posts from wrapper if needed (e.g. e621's {"posts": [...]})
        if self.is_wrapped:
            raw_posts = data.get("posts", []) if isinstance(data, dict) else []
        else:
            raw_posts = data if isinstance(data, list) else []

        # Normalise and apply local tag filtering
        normalised = []
        if extra_tags:
            required = {t.lower() for t in extra_tags if not t.startswith('~') and not t.startswith('-')}
            excluded = {t.lower()[1:] for t in extra_tags if t.startswith('-')}
            optional = {t.lower()[1:] for t in extra_tags if t.startswith('~')}
        else:
            required = excluded = optional = set()

        for raw in raw_posts:
            item = self.normalize_post(raw)
            if item is None:
                continue

            if extra_tags:
                post_tags = {t.lower() for t in item.get("tags", [])}
                if required and not required.issubset(post_tags):
                    continue
                if excluded and any(et in post_tags for et in excluded):
                    continue
                if optional and not any(ot in post_tags for ot in optional):
                    continue

            normalised.append(item)

        return normalised[:limit], len(raw_posts)
