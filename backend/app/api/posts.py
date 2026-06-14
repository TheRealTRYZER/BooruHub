"""Posts API — feed, search, tag suggestions."""
import logging
from typing import List, Optional, Union, Dict
from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, Query, BackgroundTasks, HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db.database import get_db
from app.db.models import User, BlacklistRule, CachedTag, Favorite, PostIndex, UserEvent
from app.api.deps import get_current_user
from app.services.booru_client import search_posts, search_multi_site
from app.services.blacklist import parse_blacklist, filter_posts
from app.services.tag_mapping import (
    get_user_mappings,
    build_lookup,
    translate_tags,
    apply_reverse_mapping,
)
from app.core.rate_limit import rate_limit

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/posts", tags=["posts"])

# Write Throttling: Track recently processed items to avoid redundant UPSERTs
# Thread-safe bounded set with automatic eviction
import asyncio as _asyncio

class _BoundedSet:
    """Thread-safe bounded set with automatic eviction."""
    __slots__ = ("_data", "_max", "_lock")

    def __init__(self, maxsize: int = 10000) -> None:
        self._data: set = set()
        self._max = maxsize
        self._lock = _asyncio.Lock()

    async def add_many(self, items) -> list:
        """Add items, returning only those that were new."""
        async with self._lock:
            new = [i for i in items if i not in self._data]
            self._data.update(new)
            if len(self._data) > self._max:
                self._data.clear()
                self._data.update(new)
            return new

    def __contains__(self, item) -> bool:
        return item in self._data


_recently_cached_tags = _BoundedSet(maxsize=10000)
_recently_indexed_posts = _BoundedSet(maxsize=20000)


class PostResponse(BaseModel):
    id: Union[int, str]
    source_site: str
    preview_url: Optional[str] = None
    sample_url: Optional[str] = None
    file_url: str
    file_ext: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    rating: Optional[str] = "g"
    score: Optional[int] = 0
    tags: List[str] = []
    md5: Optional[str] = None
    is_dislike: Optional[bool] = False
    duplicate_sites: Optional[List[str]] = None
    duplicates: Optional[List["PostResponse"]] = None
    parent_id: Optional[int] = None
    has_children: Optional[bool] = False
    tags_metadata: Optional[Dict[str, str]] = None


class FeedResponse(BaseModel):
    posts: List[PostResponse]
    page: int
    total: int
    unfiltered_count: int
    resolved_tags: str
    corrected_tags: Optional[str] = None


class TagSuggestion(BaseModel):
    tag: str
    is_mapped: bool = False
    from_danbooru: bool = False
    from_e621: bool = False
    from_rule34: bool = False
    category: Optional[str] = None
    post_count: Optional[int] = None


class TagSuggestionResponse(BaseModel):
    suggestions: List[TagSuggestion]



# ------------------------------------------------------------------ #
#  Helpers                                                            #
# ------------------------------------------------------------------ #

async def _get_user_blacklist(user_id: int, db: AsyncSession) -> List[BlacklistRule]:
    result = await db.execute(
        select(BlacklistRule).where(
            BlacklistRule.user_id == user_id,
            BlacklistRule.is_active == True,  # noqa: E712
        )
    )
    return result.scalars().all()


async def _get_user_dislikes(user_id: int, db: AsyncSession) -> set:
    result = await db.execute(
        select(Favorite.source_site, Favorite.post_id).where(
            Favorite.user_id == user_id,
            Favorite.is_dislike == True,  # noqa: E712
        )
    )
    return set((row[0], str(row[1])) for row in result.all())


def _apply_blacklist(posts: List[dict], rules: List[BlacklistRule], dislikes: set = None) -> List[dict]:
    if dislikes:
        posts = [p for p in posts if (p.get("source_site"), str(p.get("id"))) not in dislikes]
    if not rules:
        return posts
    bl_text = "\n".join(r.rule_line for r in rules)
    groups = parse_blacklist(bl_text)
    return filter_posts(posts, groups)


import re

def _extract_md5_from_url(url: str) -> Optional[str]:
    if not url:
        return None
    # Look for a 32-character hex string in the path/filename
    match = re.search(r'\b([a-fA-F0-9]{32})\b', url)
    if match:
        return match.group(1).lower()
    return None

def _extract_source_id(source_url: str) -> Optional[str]:
    if not source_url:
        return None
    # Pixiv artwork / illust ID
    pixiv_match = re.search(r'pixiv\.net/(?:.*/)?artworks/(\d+)', source_url)
    if pixiv_match:
        return f"pixiv:{pixiv_match.group(1)}"
    pixiv_query_match = re.search(r'illust_id=(\d+)', source_url)
    if pixiv_query_match:
        return f"pixiv:{pixiv_query_match.group(1)}"
        
    # Direct Pixiv image URL matching (e.g. i.pximg.net/.../12345678_p0.png)
    pximg_match = re.search(r'pximg\.net/.*/(\d+)_p\d+', source_url)
    if pximg_match:
        return f"pixiv:{pximg_match.group(1)}"
        
    # Twitter status ID
    twitter_match = re.search(r'(?:twitter|x)\.com/[^/]+/status/(\d+)', source_url)
    if twitter_match:
        return f"twitter:{twitter_match.group(1)}"
        
    # Cross-site Danbooru ID in source
    danbooru_match = re.search(r'danbooru\.donmai\.us/posts/(\d+)', source_url)
    if danbooru_match:
        return f"danbooru:{danbooru_match.group(1)}"

    # Cross-site e621 ID in source
    e621_match = re.search(r'e621\.net/posts/(\d+)', source_url)
    if e621_match:
        return f"e621:{e621_match.group(1)}"

    # Cross-site Rule34 ID in source
    rule34_match = re.search(r'rule34\.xxx/index\.php\?page=post&s=view&id=(\d+)', source_url)
    if rule34_match:
        return f"rule34:{rule34_match.group(1)}"
        
    return None

def _are_duplicates(a: dict, b: dict) -> bool:
    if a.get("source_site") and b.get("source_site") and a.get("source_site") == b.get("source_site"):
        return False

    # 1. Compare MD5s (either direct or from URL)
    md5_a = (a.get("md5") or "").strip().lower() or _extract_md5_from_url(a.get("file_url") or "") or _extract_md5_from_url(a.get("sample_url") or "")
    md5_b = (b.get("md5") or "").strip().lower() or _extract_md5_from_url(b.get("file_url") or "") or _extract_md5_from_url(b.get("sample_url") or "")
    if md5_a and md5_b and md5_a == md5_b:
        return True

    # 2. Compare Source IDs
    src_a = a.get("source") or ""
    src_b = b.get("source") or ""
    if src_a and src_b:
        id_a = _extract_source_id(src_a)
        id_b = _extract_source_id(src_b)
        if id_a and id_b and id_a == id_b:
            # If they have different MD5s, they might be different pages of the same gallery.
            # Only match if they share at least 60% of their tags (Jaccard similarity).
            tags_a = set(a.get("tags", []))
            tags_b = set(b.get("tags", []))
            if tags_a and tags_b:
                intersection = tags_a & tags_b
                if len(intersection) / len(tags_a | tags_b) >= 0.60:
                    return True
            else:
                return True

    # 3. Exact Dimension match + sharing a high amount of tags
    w_a, h_a = a.get("width"), a.get("height")
    w_b, h_b = b.get("width"), b.get("height")
    if w_a and h_a and w_b and h_b and w_a > 100 and h_a > 100:
        if w_a == w_b and h_a == h_b:
            tags_a = set(a.get("tags", []))
            tags_b = set(b.get("tags", []))
            intersection = tags_a & tags_b
            if tags_a and len(intersection) / len(tags_a | tags_b) >= 0.60:
                return True
                
        # 4. Aspect Ratio match + sharing a high amount of tags
        ratio_a = w_a / h_a
        ratio_b = w_b / h_b
        if abs(ratio_a - ratio_b) / max(ratio_a, ratio_b) < 0.005:
            tags_a = set(a.get("tags", []))
            tags_b = set(b.get("tags", []))
            intersection = tags_a & tags_b
            if tags_a and len(intersection) / len(tags_a | tags_b) >= 0.60:
                return True

    return False

def _merge_duplicate_posts(posts: List[dict]) -> List[dict]:
    """Group/merge duplicate posts together rather than discarding them."""
    if not posts:
        return []

    groups: List[List[dict]] = []
    
    for post in posts:
        matched = False
        for g in groups:
            if _are_duplicates(post, g[0]):
                g.append(post)
                matched = True
                break
        if not matched:
            groups.append([post])

    site_priority = {"danbooru": 3, "e621": 2, "rule34": 1}
    merged_posts: List[dict] = []
    
    for g in groups:
        if len(g) == 1:
            merged_posts.append(g[0])
            continue
            
        # Sort group to pick primary post
        g.sort(key=lambda p: (site_priority.get(p.get("source_site"), 0), p.get("score", 0)), reverse=True)
        primary = g[0]
        duplicates = g[1:]
        
        duplicate_sites = []
        unique_duplicates = []
        seen_sites = set()
        
        for d in duplicates:
            site = d.get("source_site")
            if site and site != primary.get("source_site") and site not in seen_sites:
                duplicate_sites.append(site)
                unique_duplicates.append(d)
                seen_sites.add(site)
        
        if unique_duplicates:
            primary["duplicate_sites"] = duplicate_sites
            primary["duplicates"] = unique_duplicates
            
        merged_posts.append(primary)
        
    return merged_posts

def _deduplicate_by_md5(posts: List[dict]) -> List[dict]:
    """Fallback stub to route existing callers to the new merge function."""
    return _merge_duplicate_posts(posts)


async def _cache_tags_task(tag_sources: List[dict], db: AsyncSession):
    """
    Expects tag_sources: [{"tag": "tagname", "source": "sitename"}, ...]
    """
    if not tag_sources:
        return
    
    tag_map = {} # tag -> data dict
    for item in tag_sources:
        tag = item.get("tag", "").strip().lower()
        source = item.get("source", "unknown")
        
        if not tag or ":" in tag:
            continue
        
        # Remove operators
        if tag.startswith(("~", "-")):
            tag = tag[1:]
        if not tag:
            continue
            
        if tag not in tag_map:
            tag_map[tag] = {
                "tag": tag, 
                "from_danbooru": False, 
                "from_e621": False, 
                "from_rule34": False
            }
        
        if source == "danbooru": tag_map[tag]["from_danbooru"] = True
        elif source == "e621": tag_map[tag]["from_e621"] = True
        elif source == "rule34": tag_map[tag]["from_rule34"] = True

    if not tag_map:
        return

    # Filter out recently cached tags (thread-safe)
    all_tags = list(tag_map.keys())
    new_tag_names = await _recently_cached_tags.add_many(all_tags)
    
    if not new_tag_names:
        return
    
    values = [tag_map[t] for t in new_tag_names]

    # Batch UPSERT
    stmt = pg_insert(CachedTag).values(values)
    stmt = stmt.on_conflict_do_update(
        index_elements=['tag'],
        set_=dict(
            usage_count=CachedTag.usage_count + 1,
            from_danbooru=CachedTag.from_danbooru | stmt.excluded.from_danbooru,
            from_e621=CachedTag.from_e621 | stmt.excluded.from_e621,
            from_rule34=CachedTag.from_rule34 | stmt.excluded.from_rule34
        )
    )

    try:
        await db.execute(stmt)
        await db.commit()
    except Exception as e:
        logger.error(f"Error caching tags: {e}")
        await db.rollback()


async def _cache_remote_tags_task(tag_sources: List[dict], db: AsyncSession):
    """
    Expects tag_sources: [{"tag": "tagname", "source": "sitename", "category": "catname", "post_count": N}, ...]
    """
    if not tag_sources:
        return
    
    tag_map = {}
    for item in tag_sources:
        tag = item.get("tag", "").strip().lower()
        source = item.get("source", "unknown")
        category = item.get("category")
        post_count = item.get("post_count", 0)
        
        if not tag or ":" in tag:
            continue
        if tag.startswith(("~", "-")):
            tag = tag[1:]
        if not tag:
            continue
            
        if tag not in tag_map:
            tag_map[tag] = {
                "tag": tag, 
                "from_danbooru": False, 
                "from_e621": False, 
                "from_rule34": False,
                "category": category,
                "post_count": post_count
            }
        
        if source == "danbooru": tag_map[tag]["from_danbooru"] = True
        elif source == "e621": tag_map[tag]["from_e621"] = True
        elif source == "rule34": tag_map[tag]["from_rule34"] = True
        
        if post_count > tag_map[tag]["post_count"]:
            tag_map[tag]["post_count"] = post_count
            
        if category:
            tag_map[tag]["category"] = category

    if not tag_map:
        return

    all_tags = list(tag_map.keys())
    new_tag_names = await _recently_cached_tags.add_many(all_tags)
    
    if not new_tag_names:
        return
    
    values = [tag_map[t] for t in new_tag_names]

    stmt = pg_insert(CachedTag).values(values)
    stmt = stmt.on_conflict_do_update(
        index_elements=['tag'],
        set_=dict(
            usage_count=CachedTag.usage_count + 1,
            from_danbooru=CachedTag.from_danbooru | stmt.excluded.from_danbooru,
            from_e621=CachedTag.from_e621 | stmt.excluded.from_e621,
            from_rule34=CachedTag.from_rule34 | stmt.excluded.from_rule34,
            category=stmt.excluded.category,
            post_count=stmt.excluded.post_count
        )
    )

    try:
        await db.execute(stmt)
        await db.commit()
    except Exception as e:
        logger.error(f"Error in background remote tag caching: {e}")
        await db.rollback()


async def _index_posts_task(posts: List[dict], db: AsyncSession):
    """Save all seen posts (id, source_site, tags) to the global post index in batches."""
    if not posts:
        return

    with_md5 = []
    without_md5 = []

    for post in posts:
        post_id = str(post.get("id", "")).strip()
        source_site = str(post.get("source_site", "")).strip()
        md5 = str(post.get("md5", "")).strip().lower()
        if not post_id or not source_site:
            continue
            
        tags = post.get("tags", [])
        tags_str = " ".join(tags) if isinstance(tags, list) else str(tags)
        
        data = {
            "source_site": source_site,
            "post_id": post_id,
            "md5": md5 if md5 else None,
            "tags_str": tags_str,
        }
        
        if md5:
            with_md5.append(data)
        else:
            without_md5.append(data)

    # Thread-safe deduplication
    md5_keys = [d['md5'] for d in with_md5]
    nomd5_keys = [f"{d['source_site']}:{d['post_id']}" for d in without_md5]

    new_md5 = await _recently_indexed_posts.add_many(md5_keys)
    new_nomd5 = await _recently_indexed_posts.add_many(nomd5_keys)

    new_md5_set = set(new_md5)
    new_nomd5_set = set(new_nomd5)

    final_with_md5 = [d for d in with_md5 if d['md5'] in new_md5_set]
    final_without_md5 = [d for d in without_md5 if f"{d['source_site']}:{d['post_id']}" in new_nomd5_set]

    try:
        if final_with_md5:
            stmt = pg_insert(PostIndex).values(final_with_md5)
            stmt = stmt.on_conflict_do_nothing(index_elements=['md5'])
            await db.execute(stmt)

        if final_without_md5:
            stmt = pg_insert(PostIndex).values(final_without_md5)
            stmt = stmt.on_conflict_do_nothing(index_elements=['source_site', 'post_id'])
            await db.execute(stmt)

        await db.commit()
    except Exception as e:
        logger.error(f"Error indexing posts: {e}")
        await db.rollback()


async def get_similar_tags(tags_str: str, db: AsyncSession) -> Optional[str]:
    """Try to find similar tags for a search query if zero results found."""
    if not tags_str:
        return None
        
    parts = tags_str.split()
    corrected = []
    changed = False
    
    for part in parts:
        # Skip metatags like order:, rating:, etc.
        if ":" in part or len(part) < 3:
            corrected.append(part)
            continue
            
        # Search for a similar tag in cached_tags using pg_trgm similarity
        # We only accept a high similarity threshold
        stmt = select(CachedTag.tag).where(
            func.similarity(CachedTag.tag, part) > 0.5
        ).order_by(
            func.similarity(CachedTag.tag, part).desc(),
            CachedTag.usage_count.desc()
        ).limit(1)
        
        result = await db.execute(stmt)
        match = result.scalar_one_or_none()
        
        if match and match != part:
            corrected.append(match)
            changed = True
        else:
            corrected.append(part)
            
    return " ".join(corrected) if changed else None


# ------------------------------------------------------------------ #
#  Endpoints                                                          #
# ------------------------------------------------------------------ #

@router.get("/feed", response_model=FeedResponse)
async def get_feed(
    background_tasks: BackgroundTasks,
    tags: str = Query("", description="Universal tags"),
    danbooru_tags: Optional[str] = Query(None),
    e621_tags: Optional[str] = Query(None),
    rule34_tags: Optional[str] = Query(None),
    sites: str = Query("danbooru,e621,rule34", description="Comma-separated sites"),
    ratios: Optional[str] = Query(None, description="Comma-separated ratios (e.g. 1,1,1)"),
    page: int = Query(1, ge=1),
    limit: int = Query(40, ge=1, le=100),
    skip_interval: bool = Query(False),
    user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _rl=Depends(rate_limit("search", max_requests=30, window_seconds=60)),
):
    site_list = [s.strip().lower() for s in sites.split(",") if s.strip()]

    # Parse ratios
    ratio_dict = None
    if ratios:
        try:
            vals = [float(v) for v in ratios.split(",")]
            ratio_dict = {site_list[i]: vals[i] for i in range(min(len(site_list), len(vals)))}
        except (ValueError, IndexError):
            pass

    # Load user data in parallel
    mappings = []
    blacklist_rules: List[BlacklistRule] = []
    dislikes_set = set()
    if user:
        mappings = await get_user_mappings(user.id, db)
        blacklist_rules = await _get_user_blacklist(user.id, db)
        dislikes_set = await _get_user_dislikes(user.id, db)

    # Build site-specific queries
    overrides = {"danbooru": danbooru_tags, "e621": e621_tags, "rule34": rule34_tags}
    lookup = build_lookup(mappings)
    tag_list = tags.split() if tags else []
    
    # Enforce rating:general for guests (override any provided rating)
    if user is None:
        is_relation_lookup = any(t.startswith(("id:", "parent:")) for t in tag_list)
        if not is_relation_lookup:
            logger.info(f"[GUEST_MODE] Enforcing rating:general for unauthorized user")
            def _is_rating_tag(t: str) -> bool:
                ct = t.lower()
                if ct.startswith(("-", "~")):
                    ct = ct[1:]
                return ct.startswith("rating:")
            tag_list = [t for t in tag_list if not _is_rating_tag(t)]
            tag_list.append("rating:general")
    else:
        logger.info(f"[USER_MODE] User {user.id} search tags: '{tags}'")

    site_queries = {}
    for site in site_list:
        if overrides.get(site):
            site_queries[site] = overrides[site]
        else:
            query = translate_tags(tag_list, site, lookup) if tag_list else ""
            if query is not None:
                site_queries[site] = query
                if tags or not user:
                    logger.info(f"[MAP] {site}: '{query}' (from '{tags}')")

    # Fetch
    posts, site_counts = await search_multi_site(
        site_queries, limit, page,
        user=user, ratios=ratio_dict, skip_interval=skip_interval,
    )

    # Check if all active queried sites failed (returned -1)
    active_failed = [s for s in site_list if site_counts.get(s) == -1]
    if len(active_failed) == len(site_list) and site_list:
        logger.error(f"[SEARCH_FAILURE] All queried providers failed: {active_failed}")
        raise HTTPException(
            status_code=502,
            detail=f"Booru providers ({', '.join(active_failed)}) are temporarily unavailable. Please try again."
        )

    # Post-processing
    if mappings:
        apply_reverse_mapping(posts, mappings)

    # Index raw posts BEFORE filtering (captures everything the API returns)
    unfiltered_total = sum(v for v in site_counts.values() if v >= 0)
    background_tasks.add_task(_index_posts_task, list(posts), db)

    posts = _apply_blacklist(posts, blacklist_rules, dislikes_set)
    posts = _merge_duplicate_posts(posts)

    # Cache ONLY tags from results to avoid saving typos
    tag_sources = []
    for p in posts:
        source = p.get("source_site")
        for t in p.get("tags", []):
            tag_sources.append({"tag": t, "source": source})
    
    if tag_sources:
        background_tasks.add_task(_cache_tags_task, tag_sources, db)

    corrected_tags = None
    if not posts and tags:
        corrected_tags = await get_similar_tags(tags, db)

    return {
        "posts": posts, 
        "page": page, 
        "total": unfiltered_total, 
        "unfiltered_count": unfiltered_total, 
        "resolved_tags": tags,
        "corrected_tags": corrected_tags
    }


@router.get("/search", response_model=FeedResponse)
async def search(
    background_tasks: BackgroundTasks,
    tags: str = Query(..., description="Search tags"),
    site: str = Query("danbooru", description="Single site to search"),
    page: int = Query(1, ge=1),
    limit: int = Query(40, ge=1, le=100),
    skip_interval: bool = Query(False),
    user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _rl=Depends(rate_limit("search", max_requests=30, window_seconds=60)),
):
    tag_list = tags.split() if tags else []
    
    # Enforce rating:general for guests (override any provided rating)
    if user is None:
        is_relation_lookup = any(t.startswith(("id:", "parent:")) for t in tag_list)
        if not is_relation_lookup:
            logger.info(f"[GUEST_MODE] Enforcing rating:general in search")
            def _is_rating_tag(t: str) -> bool:
                ct = t.lower()
                if ct.startswith(("-", "~")):
                    ct = ct[1:]
                return ct.startswith("rating:")
            tag_list = [t for t in tag_list if not _is_rating_tag(t)]
            tag_list.append("rating:general")
    else:
        logger.info(f"[USER_MODE] User {user.id} search tags: '{tags}'")

    mappings = []
    blacklist_rules: List[BlacklistRule] = []
    dislikes_set = set()
    if user:
        mappings = await get_user_mappings(user.id, db)
        blacklist_rules = await _get_user_blacklist(user.id, db)
        dislikes_set = await _get_user_dislikes(user.id, db)

    lookup = build_lookup(mappings)
    query_str = translate_tags(tag_list, site, lookup)

    if query_str is None:
        posts = []
        unfiltered_total = 0
    else:
        posts, unfiltered_total = await search_posts(
            site, query_str, limit, page,
            user=user, skip_interval=skip_interval,
        )
        if unfiltered_total == -1:
            logger.error(f"[SEARCH_FAILURE] Single site provider {site} failed")
            raise HTTPException(
                status_code=502,
                detail=f"Booru provider ({site}) is temporarily unavailable. Please try again."
            )

    if mappings:
        apply_reverse_mapping(posts, mappings)

    # Index raw posts BEFORE filtering (captures everything the API returns)
    background_tasks.add_task(_index_posts_task, list(posts), db)

    posts = _apply_blacklist(posts, blacklist_rules, dislikes_set)
    posts = _merge_duplicate_posts(posts)

    # Cache ONLY tags from results to avoid saving typos
    tag_sources = []
    for p in posts:
        source = p.get("source_site")
        for t in p.get("tags", []):
            tag_sources.append({"tag": t, "source": source})
        
    if tag_sources:
        background_tasks.add_task(_cache_tags_task, tag_sources, db)
    
    corrected_tags = None
    if not posts and tags:
        corrected_tags = await get_similar_tags(tags, db)

    return {
        "posts": posts, 
        "page": page, 
        "total": unfiltered_total, 
        "unfiltered_count": unfiltered_total, 
        "resolved_tags": tags,
        "corrected_tags": corrected_tags
    }


@router.get("/tags/suggest", response_model=TagSuggestionResponse)
async def suggest_tags(
    background_tasks: BackgroundTasks,
    q: str = Query(..., min_length=1, description="Tag prefix"),
    limit: int = Query(15, ge=1, le=50),
    user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q_lower = q.lower()
    
    # Extract operator prefix if present
    op_prefix = ""
    if q_lower.startswith(("-", "~")):
        op_prefix = q_lower[0]
        q_lower = q_lower[1:]

    # 1. Fetch user search counts from UserEvent (limit to last 200 search events for performance)
    tag_search_counts = {}
    if user:
        try:
            result = await db.execute(
                select(UserEvent.query)
                .where(UserEvent.user_id == user.id, UserEvent.type == "search")
                .order_by(UserEvent.ts.desc())
                .limit(200)
            )
            queries = result.scalars().all()
            for q_str in queries:
                if q_str:
                    for tag in q_str.split():
                        tag = tag.strip().lower()
                        if tag.startswith(("-", "~")):
                            tag = tag[1:]
                        if tag:
                            tag_search_counts[tag] = tag_search_counts.get(tag, 0) + 1
        except Exception as e:
            logger.error(f"Error fetching user search counts: {e}")

    # Gather candidates from all sources
    candidates = []
    seen_tags = set()
    global_popularity_map = {}

    # Source A: Mapped tags (Starter + User)
    mapped_unitags = set()
    from app.core.defaults import STARTER_MAPPINGS
    for m in STARTER_MAPPINGS:
        mapped_unitags.add(m["unitag"])
    
    if user:
        try:
            user_mappings = await get_user_mappings(user.id, db)
            for m in user_mappings:
                mapped_unitags.add(m.unitag)
        except Exception as e:
            logger.error(f"Error fetching user mappings for suggest: {e}")
            
    for unitag in mapped_unitags:
        tag_name = unitag.lower()
        if tag_name.startswith(q_lower):
            full_tag = f"{op_prefix}{unitag}"
            if full_tag not in seen_tags:
                candidates.append(TagSuggestion(tag=full_tag, is_mapped=True))
                seen_tags.add(full_tag)

    # Source B: Meta-tag suggestions
    if not op_prefix:
        meta_suggests = {
            "order:": ["score", "rank", "id", "hot", "change", "favcount", "random"],
            "rating:": ["general", "sensitive", "questionable", "explicit", "g", "s", "q", "e"],
        }
        
        for p, values in meta_suggests.items():
            if p.startswith(q_lower):
                if p not in seen_tags:
                    candidates.append(TagSuggestion(tag=p, is_mapped=False))
                    seen_tags.add(p)
            if q_lower.startswith(p):
                sub_q = q_lower[len(p):]
                for val in values:
                    if val.startswith(sub_q):
                        full_p = f"{p}{val}"
                        if full_p not in seen_tags:
                            candidates.append(TagSuggestion(tag=full_p, is_mapped=False))
                            seen_tags.add(full_p)

    # Source C: Async parallel remote autocomplete fetches
    remote_suggestions = []
    import sys
    in_pytest = "pytest" in sys.modules
    
    if q_lower and ":" not in q_lower and len(q_lower) >= 2 and not in_pytest:
        from app.services.booru import PROVIDERS
        from fastapi import BackgroundTasks
        
        tasks = []
        for site, provider in PROVIDERS.items():
            tasks.append(provider.autocomplete_tags(q_lower, user))
        
        try:
            # 3-second timeout to keep the search bar incredibly responsive
            results = await _asyncio.wait_for(_asyncio.gather(*tasks, return_exceptions=True), timeout=3.0)
            
            tag_sources_to_cache = []
            for res in results:
                if isinstance(res, list):
                    for item in res:
                        remote_suggestions.append(item)
                        tag_sources_to_cache.append({
                            "tag": item["tag"],
                            "source": "danbooru" if item["from_danbooru"] else "e621" if item["from_e621"] else "rule34",
                            "category": item["category"],
                            "post_count": item["post_count"]
                        })
            
            # Queue to background task so the autocomplete response returns instantly
            if tag_sources_to_cache:
                pass
        except Exception as e:
            logger.error(f"Error gathering remote autocompletes: {e}")

    # Source D: Global cached tags (Fetch up to 100 matching tags)
    if q_lower:
        try:
            result = await db.execute(
                select(CachedTag)
                .where(CachedTag.tag.like(f"{q_lower}%"))
                .order_by(CachedTag.usage_count.desc())
                .limit(100)
            )
            cached_tags = result.scalars().all()
            for ct in cached_tags:
                full_tag = f"{op_prefix}{ct.tag}"
                global_popularity_map[ct.tag.lower()] = ct.usage_count
                if full_tag not in seen_tags:
                    ct_category = getattr(ct, "category", None)
                    ct_post_count = getattr(ct, "post_count", None)
                    
                    candidates.append(TagSuggestion(
                        tag=full_tag, 
                        is_mapped=False,
                        from_danbooru=ct.from_danbooru,
                        from_e621=ct.from_e621,
                        from_rule34=ct.from_rule34,
                        category=ct_category if isinstance(ct_category, str) else None,
                        post_count=ct_post_count if isinstance(ct_post_count, int) else None
                    ))
                    seen_tags.add(full_tag)
        except Exception as e:
            logger.error(f"Error fetching cached tags for suggest: {e}")

    # Merge remote suggestions into candidates
    for item in remote_suggestions:
        full_tag = f"{op_prefix}{item['tag']}"
        if full_tag not in seen_tags:
            candidates.append(TagSuggestion(
                tag=full_tag,
                is_mapped=False,
                from_danbooru=item["from_danbooru"],
                from_e621=item["from_e621"],
                from_rule34=item["from_rule34"],
                category=item["category"],
                post_count=item["post_count"]
            ))
            seen_tags.add(full_tag)
        else:
            # If it was already in cached tags, update fields with richer remote data
            existing = next((c for c in candidates if c.tag == full_tag), None)
            if existing:
                if item["post_count"] and (not existing.post_count or item["post_count"] > existing.post_count):
                    existing.post_count = item["post_count"]
                if item["category"] and not existing.category:
                    existing.category = item["category"]

    # Custom sorting function
    def get_sort_key(suggestion: TagSuggestion):
        tag_name = suggestion.tag.lower()
        if tag_name.startswith(("-", "~")):
            tag_name = tag_name[1:]
        if tag_name.endswith(":"):
            tag_name = tag_name[:-1]
            
        # 1. Primary: Personal search frequency
        search_count = tag_search_counts.get(tag_name, 0)
        
        # 2. Secondary: Category priority (mapped, then meta, then has real count, then standard)
        if suggestion.is_mapped:
            category_priority = 4
        elif ":" in suggestion.tag:
            category_priority = 3
        elif suggestion.post_count:
            category_priority = 2
        else:
            category_priority = 1
            
        # 3. Tertiary: Popularity (post_count from remote / local popularity count)
        popularity = suggestion.post_count or global_popularity_map.get(tag_name, 0)
        
        return (search_count, category_priority, popularity)

    # Sort candidates descending
    candidates.sort(key=get_sort_key, reverse=True)

    # Background cache remote tags task trigger
    if q_lower and ":" not in q_lower and len(q_lower) >= 2 and 'tag_sources_to_cache' in locals() and tag_sources_to_cache:
        background_tasks.add_task(_cache_remote_tags_task, tag_sources_to_cache, db)

    return {"suggestions": candidates[:limit]}

