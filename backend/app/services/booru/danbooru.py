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
        Prioritizes 'order:' and content tags for API, leaves 'rating:' for local filtering if over limit.
        """
        clean = tags.strip()
        if not clean: return "", []
        
        all_tags = clean.split()
        
        # 1. Mandatory API tags (priorities)
        orders = [t for t in all_tags if t.startswith("order:")]
        content = [t for t in all_tags if not t.startswith(("order:", "rating:"))]
        ratings = [t for t in all_tags if t.startswith("rating:")]
        
        # Limit optimization: pick 2 best tags for the API
        api_list = []
        
        # Priority 1: order: (max 1, otherwise it conflicts/breaks)
        if orders:
            api_list.append(orders[0])
            
        # Priority 2: most important content tag (the first one)
        if content and len(api_list) < 2:
            api_list.append(content[0])
            
        # Priority 3: rating: (if we still have room)
        if ratings and len(api_list) < 2:
            api_list.append(ratings[0])
            
        # Priority 4: second content tag if room
        if len(content) > 1 and len(api_list) < 2:
            api_list.append(content[1])
            
        # Score floor injection for order:score to prevent Danbooru 500s
        # Only inject if we have 'order:score' and room in api_list
        if any(t == "order:score" for t in api_list) and len(api_list) < 2:
            api_list.append("score:>=10")

        api_tags = " ".join(api_list)
        
        # Everything else goes to local filtering
        # Note: order tags NOT in api_list are useless globally but we keep them for debug? No.
        extra_tags = [t for t in all_tags if t not in api_list and not t.startswith("order:") and t != "score:>=10"]
        
        return api_tags, extra_tags

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
            
            # Inject rating as a meta-tag for local filtering
            r = post.get("rating", "g").lower()
            if r == "e":
                post_tags.add("rating:explicit")
            elif r == "q":
                post_tags.add("rating:questionable")
            elif r == "s":
                post_tags.add("rating:sensitive")
                post_tags.add("rating:safe")
            elif r == "g":
                post_tags.add("rating:general")
                post_tags.add("rating:safe")
            
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

        return normalised, len(raw_posts)

    def normalize_post(self, raw: dict) -> Optional[dict]:
        # Extract variants mapping for robust fallbacks
        media_asset = raw.get("media_asset") or {}
        variants = media_asset.get("variants") or []
        variants_dict = {v.get("type"): v.get("url") for v in variants if v.get("type") and v.get("url")}
        
        # Align URL prioritization with the user's CLI downloader logic:
        # Prioritize large_file_url (the web-optimized sample version) over file_url (original)
        # to ensure high compatibility, fast load times, and bypass hotlinking restrictions.
        file_url = (
            raw.get("large_file_url")
            or raw.get("file_url")
            or variants_dict.get("sample")
            or variants_dict.get("original")
            or (list(variants_dict.values())[0] if variants_dict else None)
        )
        if not file_url:
            return None

        # 2. sample_url: prioritize root large_file_url, fallback to sample/original variants, fallback to file_url
        sample_url = (
            raw.get("large_file_url")
            or raw.get("file_url")
            or variants_dict.get("sample")
            or variants_dict.get("720x720")
            or variants_dict.get("original")
            or file_url
        )

        # 3. preview_url: prioritize root preview_file_url, fallback to 180x180/360x360 variants, fallback to sample_url
        preview = (
            raw.get("preview_file_url")
            or variants_dict.get("180x180")
            or variants_dict.get("360x360")
            or sample_url
        )

        tag_str = raw.get("tag_string", "")
        return {
            "id": str(raw["id"]),
            "source_site": "danbooru",
            "preview_url": preview,
            "sample_url": sample_url,
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
