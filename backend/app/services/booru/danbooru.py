"""Danbooru provider.

Quirks handled:
- Basic accounts limited to 2 tags per query (extra tags filtered locally)
- order:score without a score floor causes 500 errors on large result sets
- Automatic fallback with progressive score floors on HTTP 500
"""
import logging
from typing import Dict, List, Optional, Tuple

import httpx

from app.services.booru.base import BaseBooru
from app.db.models import User

logger = logging.getLogger(__name__)


class Danbooru(BaseBooru):
    def __init__(self) -> None:
        super().__init__()
        self.base_url = "https://danbooru.donmai.us"
        self.posts_path = "/posts.json"
        self.max_per_page = 200
        self.auth_fields = [
            ("danbooru_login", "danbooru_api_key", "DANBOORU_LOGIN", "DANBOORU_API_KEY"),
        ]

    def prepare_tags(self, tags: str) -> Tuple[str, List[str]]:
        """Split tags into API-compatible (max 2) and local-filtering tags.
        Meta-tags (order, rating, etc.) MUST go to API to avoid broken local filtering.
        """
        clean = tags.strip()
        if not clean:
            return "", []
            
        all_tags = clean.split()
        
        # 1. Enforce score floor for ranking tags if possible
        ranking_tags = ("order:rank", "order:score", "order:hot")
        if any(t in all_tags for t in ranking_tags):
            if not any(t.startswith("score:") for t in all_tags) and len(all_tags) < 2:
                all_tags.insert(0, "score:>=10")
        
        # 2. Take first 2 tags for the API (Danbooru limit)
        api_tags_list = all_tags[:2]
        
        # 3. Filter extra tags: exclude meta tags that can't be filtered locally
        # (local filter can only check for presence/absence of tokens in tag_string)
        extra_tags = [t for t in all_tags[2:] if ":" not in t]
        
        return " ".join(api_tags_list), extra_tags

    async def fetch_posts(
        self,
        tags: str,
        page: int,
        limit: int,
        user: Optional[User],
        timeout: float = 30.0,
    ) -> Tuple[List[dict], int]:
        """Fetch with local filtering for tags 3+."""
        api_tags, extra_tags = self.prepare_tags(tags)
        
        # Fetching more posts if filtering is needed
        fetch_limit = limit * 3 if extra_tags else limit
        fetch_limit = min(fetch_limit, self.max_per_page)
        
        actual_page = self.calculate_page(page, limit)
        auth_params = self.get_auth_params(user)

        params = {
            **self.default_params,
            "tags": api_tags,
            "limit": fetch_limit,
            "page": actual_page,
            **auth_params,
        }

        url = f"{self.base_url}{self.posts_path}"
        client = self._get_client(timeout)

        try:
            resp = await client.get(url, params=params)
            
            # Handle 500 error fallback (common on Danbooru for large tag sets)
            if resp.status_code == 500 and "order:score" in api_tags:
                logger.info("Danbooru 500 -> trying score floors")
                for floor in (1000, 500, 100):
                    retry_params = {**params, "tags": f"score:>={floor} {api_tags}"}
                    r = await client.get(url, params=retry_params)
                    if r.status_code == 200:
                        resp = r
                        break

            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            logger.warning(f"[Danbooru] Fetch failed: {e}")
            return [], 0

        raw_posts = data if isinstance(data, list) else []
        normalised = []
        
        # Filter by extra tags locally (supports -, ~ and required tags)
        required = {t.lower() for t in extra_tags if not t.startswith('~') and not t.startswith('-')}
        excluded = {t.lower()[1:] for t in extra_tags if t.startswith('-')}
        optional = {t.lower()[1:] for t in extra_tags if t.startswith('~')}
        
        for raw in raw_posts:
            post = self.normalize_post(raw)
            if not post:
                continue
                
            post_tags = {t.lower() for t in post.get("tags", [])}
            
            # Debug: Log tags for the very first post to see what's happening
            if raw == raw_posts[0]:
                logger.info(f"[Danbooru] Debug post tags: {list(post_tags)[:20]}...")
            
            # Match logic
            if required and not required.issubset(post_tags):
                continue
            if excluded and any(et in post_tags for et in excluded):
                continue
            if optional and not any(ot in post_tags for ot in optional):
                continue
            
            normalised.append(post)

        if extra_tags:
            logger.info(f"[Danbooru] Local filter: {len(normalised)}/{len(raw_posts)} posts matched extra tags {extra_tags}")

        return normalised[:limit], len(raw_posts)

    def normalize_post(self, raw: dict) -> Optional[dict]:
        file_url = raw.get("file_url") or raw.get("large_file_url")
        if not file_url:
            return None

        preview = (
            raw.get("preview_file_url")
            or raw.get("media_asset", {}).get("variants", [{}])[0].get("url", "")
        )

        tag_str = raw.get("tag_string", "")
        return {
            "id": str(raw["id"]),
            "source_site": "danbooru",
            "preview_url": preview,
            "sample_url": raw.get("large_file_url") or file_url,
            "file_url": file_url,
            "tags": tag_str.split() if tag_str else [],
            "rating": raw.get("rating") or "g",
            "score": raw.get("score", 0),
            "width": raw.get("image_width", 0),
            "height": raw.get("image_height", 0),
            "file_ext": raw.get("file_ext", ""),
            "md5": raw.get("md5", ""),
            "created_at": raw.get("created_at", ""),
        }
