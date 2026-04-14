"""Rule34 provider.

Quirks handled:
- Uses DAPI interface with special query params (page=dapi, s=post, q=index)
- Pagination via offset (pid) instead of page numbers
- JSON API now requires authentication (user_id + api_key)
- May return a plain string "Missing authentication" instead of JSON
- Tags are a single space-separated string, not an array
"""
import logging
from typing import Dict, List, Optional

import httpx

from app.services.booru.base import BaseBooru
from app.db.models import User

logger = logging.getLogger(__name__)

_RATING_MAP = {"safe": "g", "general": "g", "sensitive": "s", "questionable": "q", "explicit": "e"}


class Rule34(BaseBooru):
    def __init__(self) -> None:
        super().__init__()
        self.base_url = "https://api.rule34.xxx"
        self.posts_path = "/index.php"
        self.max_per_page = 1000
        self.page_param = "pid"
        self.start_page = 0
        self.default_params = {
            "page": "dapi",
            "s": "post",
            "q": "index",
            "json": "1",
        }
        self.auth_fields = [
            ("rule34_user_id", "rule34_api_key", "RULE34_USER_ID", "RULE34_API_KEY"),
        ]

    def _auth_param_name(self, field_name: str) -> str:
        """Rule34 uses 'user_id'/'api_key' directly — override base mapping."""
        mapping = {
            "rule34_user_id": "user_id",
            "rule34_api_key": "api_key",
        }
        return mapping.get(field_name, field_name)

    def calculate_page(self, page: int, limit: int) -> int:
        """Rule34 uses offset-based pagination (pid = offset)."""
        return (page - 1) * limit

    async def fetch_posts(
        self,
        tags: str,
        page: int,
        limit: int,
        user: Optional[User],
        timeout: float = 30.0,
    ) -> Tuple[List[dict], int]:
        """Override fetch_posts to handle Rule34's 'Missing authentication' quirk
        where a 200 response contains a plain string instead of JSON."""
        actual_tags = self.prepare_tags(tags)
        auth_params = self.get_auth_params(user)

        params = {
            **self.default_params,
            "tags": actual_tags,
            "limit": min(limit, self.max_per_page),
            "pid": self.calculate_page(page, limit),
            **auth_params,
        }

        url = f"{self.base_url}{self.posts_path}"
        client = self._get_client(timeout)

        try:
            resp = await client.get(url, params=params)
            if resp.status_code != 200:
                return [], 0

            text = resp.text.strip()
            if not text:
                return [], 0

            if "Missing authentication" in text:
                logger.error(
                    "[rule34] API requires authentication. "
                    "Set User ID and API Key in Settings → Rule34."
                )
                return [], 0

            # Safety check: if it looks like XML or not like JSON, skip
            if text.startswith("<") or not (text.startswith("[") or text.startswith("{")):
                return [], 0

            data = resp.json()
            if not isinstance(data, list):
                return [], 0

            return [p for p in (self.normalize_post(r) for r in data) if p][:limit]

        except (httpx.RequestError, ValueError, Exception) as e:
            logger.error(f"[rule34] Request failed: {e}")
            return [], 0

    def normalize_post(self, raw: dict) -> Optional[dict]:
        file_url = raw.get("file_url")
        if not file_url:
            return None

        rating = raw.get("rating", "explicit")
        tag_str = raw.get("tags", "")

        # Extract extension from URL
        ext = ""
        if "." in file_url:
            ext = file_url.split("?")[0].rsplit(".", 1)[-1].lower()

        return {
            "id": str(raw.get("id", "")),
            "source_site": "rule34",
            "preview_url": raw.get("preview_url", ""),
            "sample_url": raw.get("sample_url") or file_url,
            "file_url": file_url,
            "tags": tag_str.split() if isinstance(tag_str, str) else [],
            "rating": _RATING_MAP.get(rating, rating[:1] if rating else "e"),
            "score": int(raw.get("score", 0)),
            "width": int(raw.get("width", 0)),
            "height": int(raw.get("height", 0)),
            "file_ext": ext,
            "md5": raw.get("hash") or raw.get("md5", ""),
            "created_at": raw.get("created_at", raw.get("change", "")),
        }
