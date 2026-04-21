"""Tag mapping service.

Translates universal tags (unitags) to site-specific tags and back.
Handles:
- Global default mappings (from core/defaults.py)
- Per-user mapping overrides (from DB)
- Reverse mapping (site tags → unitags for blacklist matching)
- Caching with TTL to avoid repeated DB queries
"""
import logging
import time
from typing import Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models import UserTagMapping
from app.core.defaults import STARTER_MAPPINGS

logger = logging.getLogger(__name__)

# In-memory cache: user_id → (mappings_list, expiry_monotonic)
_CACHE: Dict[int, tuple] = {}
_CACHE_TTL = 300  # 5 minutes
_CACHE_MAX = 512


async def get_user_mappings(user_id: int, db: AsyncSession) -> List[UserTagMapping]:
    """Fetch user's tag mappings with in-memory caching."""
    now = time.monotonic()

    cached = _CACHE.get(user_id)
    if cached is not None:
        mappings, expiry = cached
        if now < expiry:
            return mappings
        del _CACHE[user_id]

    result = await db.execute(
        select(UserTagMapping).where(UserTagMapping.user_id == user_id)
    )
    mappings = result.scalars().all()

    _CACHE[user_id] = (mappings, now + _CACHE_TTL)
    if len(_CACHE) > _CACHE_MAX:
        _CACHE.clear()

    return mappings


def invalidate_user_cache(user_id: int) -> None:
    """Call after mapping CRUD operations to bust the cache."""
    _CACHE.pop(user_id, None)


def build_lookup(mappings: List[UserTagMapping]) -> Dict[str, Dict[str, str]]:
    """Build a unitag → {site: tags} lookup dict from defaults + user overrides."""
    lookup: Dict[str, Dict[str, str]] = {}

    # Layer 1: global defaults
    for sm in STARTER_MAPPINGS:
        u = sm["unitag"].lower()
        lookup[u] = {
            "danbooru": sm["danbooru_tags"],
            "e621": sm["e621_tags"],
            "rule34": sm["rule34_tags"],
        }

    # Layer 2: user overrides (take priority)
    for m in mappings:
        u = m.unitag.lower()
        lookup[u] = {
            "danbooru": m.danbooru_tags,
            "e621": m.e621_tags,
            "rule34": m.rule34_tags,
        }

    return lookup


def translate_tags(
    tags: List[str],
    site: str,
    lookup: Dict[str, Dict[str, str]],
) -> Optional[str]:
    """Translate a list of unitags to site-specific query string.
    Correctly handles prefixes like ~ and -.
    """
    site_tags: List[str] = []

    for tag in tags:
        tag_lower = tag.lower()
        prefix = ""
        
        if tag_lower.startswith(("~", "-")):
            prefix = tag_lower[0]
            tag_name = tag_lower[1:]
        else:
            tag_name = tag_lower

        if tag_name in lookup:
            site_val = lookup[tag_name].get(site, "").strip()
            if not site_val:
                logger.debug(f"[MAP] Site {site} disabled by unitag '{tag_name}'")
                return None
            
            # Map comma-separated values
            parts = [p.strip() for p in site_val.split(",") if p.strip()]
            if len(parts) > 1 and not prefix:
                # Automagically treat multiple alternatives as OR
                if site == "danbooru":
                    # Danbooru strict limit check: OR consumes multiple slots.
                    # Best effort: use only the first (main) tag to avoid breaking 2-tag limit.
                    site_tags.append(parts[0])
                else:
                    # e621/Rule34: use ~prefix
                    for part in parts:
                        site_tags.append(f"~{part}")
            else:
                # Standard application of prefix (empty, ~, or -)
                for part in parts:
                    site_tags.append(f"{prefix}{part}")
        else:
            site_tags.append(tag)

    return " ".join(site_tags)


def apply_reverse_mapping(
    posts: List[dict],
    mappings: List[UserTagMapping],
) -> None:
    """Inject unitags into post tag lists so blacklist rules can match them."""
    reverse: Dict[str, Dict[str, str]] = {
        "danbooru": {},
        "e621": {},
        "rule34": {},
    }

    for m in mappings:
        for t in (x.strip() for x in m.danbooru_tags.split(",") if x.strip()):
            reverse["danbooru"][t.lower()] = m.unitag
        for t in (x.strip() for x in m.e621_tags.split(",") if x.strip()):
            reverse["e621"][t.lower()] = m.unitag
        for t in (x.strip() for x in m.rule34_tags.split(",") if x.strip()):
            reverse["rule34"][t.lower()] = m.unitag

    for post in posts:
        site = post.get("source_site")
        rmap = reverse.get(site)
        if not rmap:
            continue
        new_tags = list(post["tags"])
        for pt in post["tags"]:
            mapped = rmap.get(pt.lower())
            if mapped and mapped not in new_tags:
                new_tags.append(mapped)
        post["tags"] = new_tags
