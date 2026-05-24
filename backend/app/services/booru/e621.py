"""E621 provider.

Quirks handled:
- Posts are wrapped in {"posts": [...]}
- Tags are nested in categorised dicts (general, species, character, …)
- Score is a nested object {"total": N}
- Rating uses 's' for safe instead of 'g'
"""
import logging
from typing import List, Optional

from app.services.booru.base import BaseBooru
from app.db.models import User

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

        def make_absolute(url: str | None) -> str:
            if url and url.startswith("/"):
                return f"https://e621.net{url}"
            return url or ""

        sources = raw.get("sources") or []
        source_str = sources[0] if isinstance(sources, list) and sources else raw.get("source") or ""

        relationships = raw.get("relationships") or {}
        p_id = relationships.get("parent_id")
        parent_id = int(p_id) if p_id is not None else None
        has_children = bool(relationships.get("has_children", False))

        # Build tag category metadata dictionary
        raw_tags_dict = raw.get("tags") or {}
        tags_metadata = {}
        cat_map = {
            "general": "general",
            "artist": "artist",
            "copyright": "copyright",
            "character": "character",
            "species": "species",
            "invalid": "invalid",
            "lore": "lore",
            "meta": "metadata"
        }
        for cat_key, cat_name in cat_map.items():
            for t in raw_tags_dict.get(cat_key, []):
                tags_metadata[t] = cat_name

        return {
            "id": str(raw["id"]),
            "source_site": "e621",
            "preview_url": make_absolute(preview_data.get("url")),
            "sample_url": make_absolute(sample_data.get("url")) or file_url,
            "file_url": file_url,
            "tags": tags,
            "rating": _RATING_MAP.get(raw.get("rating", "s"), "g"),
            "score": score,
            "width": file_data.get("width", 0),
            "height": file_data.get("height", 0),
            "file_ext": file_data.get("ext", ""),
            "md5": file_data.get("md5", ""),
            "source": source_str,
            "created_at": raw.get("created_at", ""),
            "parent_id": parent_id,
            "has_children": has_children,
            "tags_metadata": tags_metadata,
        }

    async def autocomplete_tags(self, q: str, user: Optional[User] = None) -> List[dict]:
        """Search tags using e621's tags API."""
        client = self._get_client()
        url = f"{self.base_url}/tags.json"
        
        search_pattern = f"*{q}*" if "*" not in q else q
        params = {
            "search[name_matches]": search_pattern,
            "search[order]": "count",
            "limit": 15
        }
        
        # Resolve user auth to prevent rate limiting
        auth = self.get_auth_params(user)
        if auth:
            params.update(auth)
            
        try:
            resp = await client.get(url, params=params)
            if resp.status_code != 200:
                return []
            
            data = resp.json()
            tags_list = data.get("tags") if isinstance(data, dict) else data
            if not isinstance(tags_list, list):
                return []
                
            results = []
            cat_map = {
                0: "general",
                1: "artist",
                3: "copyright",
                4: "character",
                5: "species",
                7: "metadata",
                8: "metadata"
            }
            
            for item in tags_list:
                if not isinstance(item, dict):
                    continue
                cat_num = item.get("category", 0)
                results.append({
                    "tag": item.get("name", ""),
                    "category": cat_map.get(cat_num, "general"),
                    "post_count": item.get("post_count", 0),
                    "from_danbooru": False,
                    "from_e621": True,
                    "from_rule34": False
                })
            return results
        except Exception as e:
            logger.error(f"Error fetching autocomplete from e621: {e}")
            return []
