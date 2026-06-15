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
            
        # Priority 3: score floor if order:score is present and no content tag (prevents 500s)
        if any(t == "order:score" for t in api_list) and not content and len(api_list) < 2:
            api_list.append("score:>=250")

        # Priority 4: rating: (if we still have room)
        if ratings and len(api_list) < 2:
            api_list.append(ratings[0])
            
        # Priority 5: second content tag if room
        if len(content) > 1 and len(api_list) < 2:
            api_list.append(content[1])
            
        # Score floor injection for order:score to prevent Danbooru 500s
        # Only inject if we have 'order:score' and room in api_list
        if any(t == "order:score" for t in api_list) and len(api_list) < 2:
            api_list.append("score:>=250")

        api_tags = " ".join(api_list)
        
        # Everything else goes to local filtering
        extra_tags = [t for t in all_tags if t not in api_list and not t.startswith("order:") and t != "score:>=250"]
        
        return api_tags, extra_tags

    async def handle_error_response(
        self,
        resp: httpx.Response,
        client: httpx.AsyncClient,
        url: str,
        params: dict,
        original_tags: str,
    ) -> httpx.Response:
        """Handle Danbooru 500 by attempting progressive score floors and/or stripping auth."""
        if resp.status_code == 500 and "order:score" in params.get("tags", ""):
            logger.info("Danbooru 500 -> trying score floors and/or stripping auth")
            
            # Clean original_tags of any existing score filters
            orig_words = original_tags.strip().split()
            filtered_words = [w for w in orig_words if not w.lower().startswith("score:")]
            base_tags = " ".join(filtered_words)

            # Step 1: Try stripping auth first with the same query (hitting cached read replica)
            if "login" in params or "api_key" in params:
                no_auth_params = {k: v for k, v in params.items() if k not in ("login", "api_key")}
                try:
                    r = await client.get(url, params=no_auth_params)
                    if r.status_code == 200:
                        logger.info("Danbooru 500 -> resolved by stripping auth")
                        return r
                except Exception as e:
                    logger.warning(f"Danbooru retry without auth failed: {e}")
            
            # Step 2: Progressive score floors starting at 250 and raising (both without and with auth)
            for floor in (250, 500, 1000, 2000):
                retry_tags = f"{base_tags} score:>={floor}"
                # Try without auth first as it's much more likely to succeed
                if "login" in params or "api_key" in params:
                    retry_params_no_auth = {
                        k: v for k, v in params.items() if k not in ("login", "api_key")
                    }
                    retry_params_no_auth["tags"] = retry_tags
                    try:
                        r = await client.get(url, params=retry_params_no_auth)
                        if r.status_code == 200:
                            logger.info(f"Danbooru 500 -> resolved with floor {floor} (no auth)")
                            return r
                    except Exception as e:
                        logger.warning(f"Danbooru retry failed for floor {floor} without auth: {e}")
                # Fallback to with auth
                retry_params = {**params, "tags": retry_tags}
                try:
                    r = await client.get(url, params=retry_params)
                    if r.status_code == 200:
                        logger.info(f"Danbooru 500 -> resolved with floor {floor} (with auth)")
                        return r
                except Exception as e:
                    logger.warning(f"Danbooru retry failed for floor {floor}: {e}")
        return resp

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
        p_id = raw.get("parent_id")
        parent_id = int(p_id) if p_id is not None else None
        
        # Build tag category metadata dictionary
        tags_metadata = {}
        for t in raw.get("tag_string_artist", "").split(): tags_metadata[t] = "artist"
        for t in raw.get("tag_string_character", "").split(): tags_metadata[t] = "character"
        for t in raw.get("tag_string_copyright", "").split(): tags_metadata[t] = "copyright"
        for t in raw.get("tag_string_general", "").split(): tags_metadata[t] = "general"
        for t in raw.get("tag_string_meta", "").split(): tags_metadata[t] = "metadata"
        
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
            "source": raw.get("source", ""),
            "created_at": raw.get("created_at", ""),
            "parent_id": parent_id,
            "has_children": bool(raw.get("has_children", False)),
            "tags_metadata": tags_metadata,
        }

    async def autocomplete_tags(self, q: str, user: Optional[User] = None) -> List[dict]:
        """Search tags using Danbooru's tags API."""
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
            if not isinstance(data, list):
                return []
                
            results = []
            cat_map = {
                0: "general",
                1: "artist",
                3: "copyright",
                4: "character",
                5: "metadata"
            }
            
            for item in data:
                if not isinstance(item, dict):
                    continue
                cat_num = item.get("category", 0)
                results.append({
                    "tag": item.get("name", ""),
                    "category": cat_map.get(cat_num, "general"),
                    "post_count": item.get("post_count", 0),
                    "from_danbooru": True,
                    "from_e621": False,
                    "from_rule34": False
                })
            return results
        except Exception as e:
            logger.error(f"Error fetching autocomplete from Danbooru: {e}")
            return []
