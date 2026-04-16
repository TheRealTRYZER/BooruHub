"""Posts API — feed, search, tag suggestions."""
import asyncio
import logging
from typing import List, Optional, Union, Dict
from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, Query, BackgroundTasks
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, insert
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db.database import get_db
from app.db.models import User, BlacklistRule, CachedTag, Favorite, PostIndex
from app.api.deps import get_current_user
from app.services.booru_client import search_posts, search_multi_site
from app.services.blacklist import parse_blacklist, filter_posts
from app.services.tag_mapping import (
    get_user_mappings,
    build_lookup,
    translate_tags,
    apply_reverse_mapping,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/posts", tags=["posts"])


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


def _deduplicate_by_md5(posts: List[dict]) -> List[dict]:
    """Remove duplicate posts from the list based on MD5 hash."""
    seen_md5 = set()
    unique_posts = []
    for post in posts:
        md5 = post.get("md5")
        if md5:
            if md5 in seen_md5:
                continue
            seen_md5.add(md5)
        unique_posts.append(post)
    return unique_posts


async def _cache_tags_task(tags: List[str], db: AsyncSession):
    if not tags:
        return
    
    clean_tags = []
    for tag in tags:
        tag = tag.strip().lower()
        if not tag or ":" in tag:
            continue
        
        # Remove operators
        if tag.startswith(("~", "-")):
            tag = tag[1:]
        if not tag:
            continue
        clean_tags.append(tag)

    if not clean_tags:
        return

    # Use a set to avoid duplicates in the current batch
    unique_clean_tags = list(set(clean_tags))
    values = [{"tag": t} for t in unique_clean_tags]

    # Batch UPSERT
    stmt = pg_insert(CachedTag).values(values)
    stmt = stmt.on_conflict_do_update(
        index_elements=['tag'],
        set_=dict(usage_count=CachedTag.usage_count + 1)
    )
    
    try:
        await db.execute(stmt)
        await db.commit()
    except Exception as e:
        logger.error(f"Error caching tags: {e}")
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

    try:
        if with_md5:
            stmt = pg_insert(PostIndex).values(with_md5)
            stmt = stmt.on_conflict_do_nothing(index_elements=['md5'])
            await db.execute(stmt)

        if without_md5:
            stmt = pg_insert(PostIndex).values(without_md5)
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
        logger.info(f"[GUEST_MODE] Enforcing rating:general for unauthorized user")
        tag_list = [t for t in tag_list if not t.startswith("rating:")]
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

    # Post-processing
    if mappings:
        apply_reverse_mapping(posts, mappings)

    # Index raw posts BEFORE filtering (captures everything the API returns)
    unfiltered_total = sum(site_counts.values())
    background_tasks.add_task(_index_posts_task, list(posts), db)

    posts = _apply_blacklist(posts, blacklist_rules, dislikes_set)
    posts = _deduplicate_by_md5(posts)

    # Cache ONLY tags from results to avoid saving typos
    unique_tags = set()
    for p in posts:
        unique_tags.update(p.get("tags", []))
    
    if unique_tags:
        background_tasks.add_task(_cache_tags_task, list(unique_tags), db)

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
):
    tag_list = tags.split() if tags else []
    
    # Enforce rating:general for guests (override any provided rating)
    if user is None:
        logger.info(f"[GUEST_MODE] Enforcing rating:general in search")
        tag_list = [t for t in tag_list if not t.startswith("rating:")]
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

    if mappings:
        apply_reverse_mapping(posts, mappings)

    # Index raw posts BEFORE filtering (captures everything the API returns)
    background_tasks.add_task(_index_posts_task, list(posts), db)

    posts = _apply_blacklist(posts, blacklist_rules, dislikes_set)
    posts = _deduplicate_by_md5(posts)

    # Cache ONLY tags from results to avoid saving typos
    unique_tags = set()
    for p in posts:
        unique_tags.update(p.get("tags", []))
        
    if unique_tags:
        background_tasks.add_task(_cache_tags_task, list(unique_tags), db)
    
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
    q: str = Query(..., min_length=1, description="Tag prefix"),
    limit: int = Query(15, ge=1, le=50),
    user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    suggestions: List[TagSuggestion] = []
    seen_tags = set()
    q_lower = q.lower()
    
    # Extract operator prefix if present
    op_prefix = ""
    if q_lower.startswith(("-", "~")):
        op_prefix = q_lower[0]
        q_lower = q_lower[1:]
    
    # 0. Collect all mapped tags (Starter + User)
    mapped_unitags = set()
    from app.core.defaults import STARTER_MAPPINGS
    for m in STARTER_MAPPINGS:
        mapped_unitags.add(m["unitag"])
    
    if user:
        user_mappings = await get_user_mappings(user.id, db)
        for m in user_mappings:
            mapped_unitags.add(m.unitag)

    # 1. Prioritize all mapped tags
    for unitag in sorted(list(mapped_unitags)):
        tag_name = unitag.lower()
        if tag_name.startswith(q_lower):
            full_tag = f"{op_prefix}{unitag}"
            if full_tag not in seen_tags:
                suggestions.append(TagSuggestion(tag=full_tag, is_mapped=True))
                seen_tags.add(full_tag)

    # 2. Provide Meta-Tag suggestions (only skip if prefix is present and meta-tags don't support it)
    if not op_prefix:
        meta_suggests = {
            "order:": ["score", "rank", "id", "hot", "change", "favcount", "random"],
            "rating:": ["general", "sensitive", "questionable", "explicit", "g", "s", "q", "e"],
        }
        
        for p, values in meta_suggests.items():
            if p.startswith(q_lower):
                if p not in seen_tags:
                    suggestions.append(TagSuggestion(tag=p, is_mapped=False))
                    seen_tags.add(p)
            if q_lower.startswith(p):
                sub_q = q_lower[len(p):]
                for val in values:
                    if val.startswith(sub_q):
                        full_p = f"{p}{val}"
                        if full_p not in seen_tags:
                            suggestions.append(TagSuggestion(tag=full_p, is_mapped=False))
                            seen_tags.add(full_p)

    # 3. Fill remaining with global cached tags, sorted by popularity
    remaining_limit = limit - len(suggestions)
    if remaining_limit > 0 and q_lower:
        result = await db.execute(
            select(CachedTag)
            .where(CachedTag.tag.like(f"{q_lower}%"))
            .order_by(CachedTag.usage_count.desc())
            .limit(remaining_limit + 20) # Over-fetch to filter duplicates and metadata results
        )
        cached_tags = result.scalars().all()
        for ct in cached_tags:
            full_tag = f"{op_prefix}{ct.tag}"
            if full_tag not in seen_tags:
                suggestions.append(TagSuggestion(tag=full_tag, is_mapped=False))
                seen_tags.add(full_tag)
                if len(suggestions) >= limit:
                    break

    return {"suggestions": suggestions[:limit]}

