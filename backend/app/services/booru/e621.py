"""E621 provider.

Quirks handled:
- Posts are wrapped in {"posts": [...]}
- Tags are nested in categorised dicts (general, species, character, …)
- Score is a nested object {"total": N}
- Rating uses 's' for safe instead of 'g'
"""
import logging
from typing import Optional

from app.services.booru.base import BaseBooru

logger = logging.getLogger(__name__)

_RATING_MAP = {"s": "g", "q": "q", "e": "e"}


class E621(BaseBooru):
    def __init__(self) -> None:
        super().__init__()
        self.base_url = "https://e621.net"
        self.posts_path = "/posts.json"
        self.max_per_page = 320
        self.is_wrapped = True
        self.user_agent = "BooruHub/1.0 (by TRYZE on e621)"
        self.auth_fields = [
            ("e621_login", "e621_api_key", "E621_LOGIN", "E621_API_KEY"),
        ]

    def normalize_post(self, raw: dict) -> Optional[dict]:
        file_data = raw.get("file", {})
        file_url = file_data.get("url")
        if not file_url:
            return None

        preview_data = raw.get("preview", {})
        sample_data = raw.get("sample", {})

        # Flatten categorised tags into a single list
        tags: list[str] = []
        for cat_list in raw.get("tags", {}).values():
            if isinstance(cat_list, list):
                tags.extend(cat_list)

        # Score can be {"total": N} or plain int
        raw_score = raw.get("score", 0)
        score = raw_score.get("total", 0) if isinstance(raw_score, dict) else raw_score

        return {
            "id": str(raw["id"]),
            "source_site": "e621",
            "preview_url": preview_data.get("url", ""),
            "sample_url": sample_data.get("url") or file_url,
            "file_url": file_url,
            "tags": tags,
            "rating": _RATING_MAP.get(raw.get("rating", "s"), "g"),
            "score": score,
            "width": file_data.get("width", 0),
            "height": file_data.get("height", 0),
            "file_ext": file_data.get("ext", ""),
            "created_at": raw.get("created_at", ""),
        }
