"""Rule34 provider.

Quirks handled:
- Uses DAPI interface with special query params (page=dapi, s=post, q=index)
- Pagination via offset (pid) instead of page numbers
- JSON API now requires authentication (user_id + api_key)
- May return a plain string "Missing authentication" instead of JSON
- Tags are a single space-separated string, not an array
"""
import logging
import re
from typing import Dict, List, Optional, Tuple

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
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
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

    def prepare_tags(self, tags: str) -> Tuple[str, List[str]]:
        """Map rating:general tags to Rule34-compatible rating:safe."""
        clean = tags.strip()
        if not clean:
            return "", []
        
        words = clean.split()
        mapped = []
        for w in words:
            lower_w = w.lower()
            if "rating:general" in lower_w:
                w = w.replace("rating:general", "rating:safe")
            elif "rating:s" in lower_w and "rating:safe" not in lower_w:
                w = w.replace("rating:s", "rating:safe")
            mapped.append(w)
        return " ".join(mapped), []

    def calculate_page(self, page: int, limit: int) -> int:
        """Rule34 uses 0-indexed page-based pagination (pid = page)."""
        return page - 1

    def modify_params(self, params: dict) -> None:
        """Extract id from tags if present for Rule34 API."""
        api_tags = params.get("tags", "")
        post_id_match = re.search(r'\bid:(\d+)\b', api_tags)
        if post_id_match:
            post_id = post_id_match.group(1)
            params["id"] = post_id
            api_tags = re.sub(r'\bid:\d+\b', '', api_tags).strip()
            params["tags"] = api_tags

    def validate_response_text(self, text: str) -> bool:
        """Validate Rule34 response text, checking for authentication and JSON format."""
        cleaned = text.strip()
        if not cleaned:
            logger.warning("[rule34] Empty response from API.")
            return False

        logger.info(f"[rule34] Response snippet: {cleaned[:100]}")

        if "Missing authentication" in cleaned:
            logger.error(
                "[rule34] API requires authentication. "
                "Set User ID and API Key in Settings → Rule34."
            )
            return False

        # Safety check: if it looks like XML or not like JSON, skip
        if cleaned.startswith("<") or not (cleaned.startswith("[") or cleaned.startswith("{")):
            return False

        return True

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

        p_id = raw.get("parent_id")
        parent_id = int(p_id) if p_id and str(p_id) != "0" else None
        
        h_child = raw.get("has_children")
        has_children = str(h_child).lower() in ("true", "1") if h_child is not None else False

        # Build tag category metadata dictionary using heuristics
        tags_metadata = {}
        for t in (tag_str.split() if isinstance(tag_str, str) else []):
            if t.endswith(("_(cosplay)", "_(character)")):
                tags_metadata[t] = "character"
            elif t.endswith(("_(artist)", "_(style)")):
                tags_metadata[t] = "artist"
            elif t.endswith(("_(anime)", "_(series)", "_(game)")):
                tags_metadata[t] = "copyright"
            else:
                tags_metadata[t] = "general"

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
            "source": raw.get("source", ""),
            "created_at": raw.get("created_at", raw.get("change", "")),
            "parent_id": parent_id,
            "has_children": has_children,
            "tags_metadata": tags_metadata,
        }

    async def autocomplete_tags(self, q: str, user: Optional[User] = None) -> List[dict]:
        """Search tags using Rule34's tags API."""
        client = self._get_client()
        url = f"{self.base_url}/index.php"
        
        search_pattern = f"{q}%"
        params = {
            "page": "dapi",
            "s": "tag",
            "q": "index",
            "json": "1",
            "name_pattern": search_pattern,
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
            tags_list = data
            if isinstance(data, dict):
                tags_list = data.get("tag", [])
            if not isinstance(tags_list, list):
                if isinstance(tags_list, dict):
                    tags_list = [tags_list]
                else:
                    return []
                
            results = []
            cat_map = {
                0: "general",
                1: "artist",
                3: "copyright",
                4: "character",
                5: "metadata"
            }
            
            for item in tags_list:
                if not isinstance(item, dict):
                    continue
                type_val = item.get("type", 0)
                try:
                    cat_num = int(type_val)
                except (ValueError, TypeError):
                    cat_num = 0
                
                try:
                    post_count = int(item.get("count", 0))
                except (ValueError, TypeError):
                    post_count = 0
                    
                results.append({
                    "tag": item.get("name", ""),
                    "category": cat_map.get(cat_num, "general"),
                    "post_count": post_count,
                    "from_danbooru": False,
                    "from_e621": False,
                    "from_rule34": True
                })
            return results
        except Exception as e:
            logger.error(f"Error fetching autocomplete from Rule34: {e}")
            return []
