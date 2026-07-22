"""Posts API — feed, search, tag suggestions."""
import asyncio as _asyncio
import logging
import threading as _threading
from collections import OrderedDict
from typing import List, Optional, Union, Dict, Tuple
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

# New service imports
from app.services.dedup import _merge_duplicate_posts
from app.services.tag_cache import (
    _cache_tags_task,
    _cache_remote_tags_task,
    _index_posts_task,
)
from app.services.tag_suggestions import get_similar_tags

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/posts", tags=["posts"])


class PostResponse(BaseModel):
    id: str  # Simplified from Union[int, str]
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
    has_more: bool = True  # Added truthful pagination flag


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


async def _get_user_interactions(user_id: int, db: AsyncSession) -> tuple[set, set]:
    result = await db.execute(
        select(Favorite.source_site, Favorite.post_id, Favorite.is_dislike).where(
            Favorite.user_id == user_id
        )
    )
    favs = set()
    dislikes = set()
    for row in result.all():
        key = (row[0], str(row[1]))
        if row[2]:
            dislikes.add(key)
        else:
            favs.add(key)
    return favs, dislikes


def _apply_blacklist(posts: List[dict], rules: List[BlacklistRule], dislikes: set = None) -> List[dict]:
    if dislikes:
        posts = [p for p in posts if (p.get("source_site"), str(p.get("id"))) not in dislikes]
    if not rules:
        return posts
    bl_text = "\n".join(r.rule_line for r in rules)
    groups = parse_blacklist(bl_text)
    return filter_posts(posts, groups)

def _inject_favorites(posts: List[dict], favs: set) -> List[dict]:
    if not favs:
        return posts
    for p in posts:
        if (p.get("source_site"), str(p.get("id"))) in favs:
            p["favorite"] = True
    return posts


def _enforce_guest_rating(tag_list: List[str], context_name: str = "general") -> List[str]:
    """Enforce rating:general for guest requests (override other rating filters)."""
    is_relation_lookup = any(t.startswith(("id:", "parent:")) for t in tag_list)
    if not is_relation_lookup:
        logger.info(f"[GUEST_MODE] Enforcing rating:general in {context_name}")
        def _is_rating_tag(t: str) -> bool:
            ct = t.lower()
            if ct.startswith(("-", "~")):
                ct = ct[1:]
            return ct.startswith("rating:")
        tag_list = [t for t in tag_list if not _is_rating_tag(t)]
        tag_list.append("rating:general")
    return tag_list


async def _process_posts(
    posts: List[dict],
    *,
    mappings: list,
    blacklist_rules: List[BlacklistRule],
    favs: set,
    dislikes: set,
    background_tasks: BackgroundTasks,
    tags_str: str,
    db: AsyncSession,
) -> tuple[List[dict], Optional[str]]:
    """Helper to apply reverse mapping, blacklist filtering, deduplication, and cache/suggest tags."""
    if mappings:
        apply_reverse_mapping(posts, mappings)

    # Index raw posts BEFORE filtering (captures everything the API returns)
    background_tasks.add_task(_index_posts_task, list(posts))

    posts = _apply_blacklist(posts, blacklist_rules, dislikes)
    posts = _inject_favorites(posts, favs)
    posts = _merge_duplicate_posts(posts)

    # Cache ONLY tags from results to avoid saving typos
    tag_sources = []
    for p in posts:
        source = p.get("source_site")
        for t in p.get("tags", []):
            tag_sources.append({"tag": t, "source": source})
    
    if tag_sources:
        background_tasks.add_task(_cache_tags_task, tag_sources)

    corrected_tags = None
    if not posts and tags_str:
        corrected_tags = await get_similar_tags(tags_str, db)

    return posts, corrected_tags


# ------------------------------------------------------------------ #
#  Endpoints                                                          #
# ------------------------------------------------------------------ #

@router.get("/feed", response_model=FeedResponse)
async def get_feed(
    background_tasks: BackgroundTasks,
    tags: str = Query("", max_length=512, description="Universal tags"),
    danbooru_tags: Optional[str] = Query(None),
    e621_tags: Optional[str] = Query(None),
    rule34_tags: Optional[str] = Query(None),
    sites: str = Query("danbooru,e621,rule34", description="Comma-separated sites"),
    ratios: Optional[str] = Query(None, description="Comma-separated ratios (e.g. 1,1,1)"),
    page: int = Query(1, ge=1),
    limit: int = Query(40, ge=1, le=200),
    skip_interval: bool = Query(False),
    user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _rl=Depends(rate_limit("search", max_requests=30, window_seconds=60)),
):
    from app.services.booru import PROVIDERS
    site_list = [s.strip().lower() for s in sites.split(",") if s.strip()]
    for site in site_list:
        if site not in PROVIDERS:
            raise HTTPException(status_code=400, detail=f"Invalid site: {site}")

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
    favs_set = set()
    dislikes_set = set()
    if user:
        mappings = await get_user_mappings(user.id, db)
        blacklist_rules = await _get_user_blacklist(user.id, db)
        favs_set, dislikes_set = await _get_user_interactions(user.id, db)

    # Build site-specific queries
    overrides = {"danbooru": danbooru_tags, "e621": e621_tags, "rule34": rule34_tags}
    lookup = build_lookup(mappings)
    tag_list = tags.split() if tags else []
    
    if user:
        logger.debug(f"[USER_MODE] User {user.id} search tags: '{tags}'")

    site_queries = {}
    for site in site_list:
        if overrides.get(site) is not None:
            site_queries[site] = overrides[site]
        else:
            query = translate_tags(tag_list, site, lookup) if tag_list else ""
            if query is not None:
                site_queries[site] = query
                if tags or not user:
                    logger.debug(f"[MAP] {site}: '{query}' (from '{tags}')")

    # Enforce rating:general for guests on all final queries (including overrides)
    if user is None:
        for s in list(site_queries.keys()):
            q_list = site_queries[s].split()
            q_list = _enforce_guest_rating(q_list, s)
            site_queries[s] = " ".join(q_list)

    # Fetch
    posts, site_counts, has_more = await search_multi_site(
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

    unfiltered_total = sum(v for v in site_counts.values() if v >= 0)

    # Post-processing helper pipeline
    posts, corrected_tags = await _process_posts(
        posts,
        mappings=mappings,
        blacklist_rules=blacklist_rules,
        favs=favs_set,
        dislikes=dislikes_set,
        background_tasks=background_tasks,
        tags_str=tags,
        db=db,
    )

    return {
        "posts": posts, 
        "page": page, 
        "total": unfiltered_total, 
        "unfiltered_count": unfiltered_total, 
        "resolved_tags": tags,
        "corrected_tags": corrected_tags,
        "has_more": has_more
    }


@router.get("/search", response_model=FeedResponse)
async def search(
    background_tasks: BackgroundTasks,
    tags: str = Query(..., max_length=512, description="Search tags"),
    site: str = Query("danbooru", description="Single site to search"),
    page: int = Query(1, ge=1),
    limit: int = Query(40, ge=1, le=200),
    skip_interval: bool = Query(False),
    user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _rl=Depends(rate_limit("search", max_requests=30, window_seconds=60)),
):
    from app.services.booru import PROVIDERS
    if site.lower() not in PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Invalid site: {site}")

    tag_list = tags.split() if tags else []
    
    # Enforce rating:general for guests (override any provided rating)
    if user is None:
        tag_list = _enforce_guest_rating(tag_list, "search")
    else:
        logger.debug(f"[USER_MODE] User {user.id} search tags: '{tags}'")

    mappings = []
    blacklist_rules: List[BlacklistRule] = []
    favs_set = set()
    dislikes_set = set()
    if user:
        mappings = await get_user_mappings(user.id, db)
        blacklist_rules = await _get_user_blacklist(user.id, db)
        favs_set, dislikes_set = await _get_user_interactions(user.id, db)

    lookup = build_lookup(mappings)
    query_str = translate_tags(tag_list, site, lookup)

    has_more = False
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
        has_more = len(posts) >= limit
        posts = posts[:limit]

    # Post-processing helper pipeline
    posts, corrected_tags = await _process_posts(
        posts,
        mappings=mappings,
        blacklist_rules=blacklist_rules,
        favs=favs_set,
        dislikes=dislikes_set,
        background_tasks=background_tasks,
        tags_str=tags,
        db=db,
    )

    return {
        "posts": posts, 
        "page": page, 
        "total": unfiltered_total, 
        "unfiltered_count": unfiltered_total, 
        "resolved_tags": tags,
        "corrected_tags": corrected_tags,
        "has_more": has_more
    }


@router.get("/tags/suggest", response_model=TagSuggestionResponse)
async def suggest_tags(
    background_tasks: BackgroundTasks,
    q: str = Query(..., min_length=1, max_length=512, description="Tag prefix"),
    limit: int = Query(15, ge=1, le=50),
    fast: bool = Query(False, description="Skip remote autocomplete fetches and return local sources only"),
    user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q_lower = q.lower()
    tag_sources_to_cache = []
    
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

    if not fast and q_lower and ":" not in q_lower and len(q_lower) >= 2 and not in_pytest:
        from app.services.booru import PROVIDERS
        from fastapi import BackgroundTasks
        
        tasks = []
        for site, provider in PROVIDERS.items():
            tasks.append(provider.autocomplete_tags(q_lower, user))
        
        try:
            # 3-second timeout to keep the search bar incredibly responsive
            results = await _asyncio.wait_for(_asyncio.gather(*tasks, return_exceptions=True), timeout=3.0)
            
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
    if tag_sources_to_cache:
        background_tasks.add_task(_cache_remote_tags_task, tag_sources_to_cache)

    return {"suggestions": candidates[:limit]}

