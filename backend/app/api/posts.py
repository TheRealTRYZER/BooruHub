"""Posts API — feed, search, tag suggestions."""
import asyncio
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.dialects.sqlite import insert
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


async def _cache_tags_task(tags: List[str], db: AsyncSession):
    if not tags:
        return
    
    for tag in tags:
        tag = tag.strip().lower()
        if not tag or ":" in tag:
            continue
        
        # Remove operators
        clean_tag = tag
        if clean_tag.startswith(("~", "-")):
            clean_tag = clean_tag[1:]
        if not clean_tag:
            continue
            
        stmt = insert(CachedTag).values(tag=clean_tag)
        stmt = stmt.on_conflict_do_update(
            index_elements=['tag'],
            set_=dict(usage_count=CachedTag.usage_count + 1)
        )
        try:
            await db.execute(stmt)
        except Exception:
            pass
    
    try:
        await db.commit()
    except Exception:
        await db.rollback()


async def _index_posts_task(posts: List[dict], db: AsyncSession):
    """Save all seen posts (id, source_site, tags) to the global post index."""
    if not posts:
        return
    for post in posts:
        post_id = str(post.get("id", "")).strip()
        source_site = str(post.get("source_site", "")).strip()
        md5 = str(post.get("md5", "")).strip().lower()
        if not post_id or not source_site:
            continue
            
        tags = post.get("tags", [])
        tags_str = " ".join(tags) if isinstance(tags, list) else str(tags)
        
        stmt = pg_insert(PostIndex).values(
            source_site=source_site,
            post_id=post_id,
            md5=md5 if md5 else None,
            tags_str=tags_str,
        )
        
        # Deduplicate by MD5 if available, otherwise by site/id
        if md5:
            stmt = stmt.on_conflict_do_nothing(index_elements=['md5'])
        else:
            stmt = stmt.on_conflict_do_nothing(index_elements=['source_site', 'post_id'])
            
        try:
            await db.execute(stmt)
        except Exception:
            pass
    try:
        await db.commit()
    except Exception:
        await db.rollback()


# ------------------------------------------------------------------ #
#  Endpoints                                                          #
# ------------------------------------------------------------------ #

@router.get("/feed")
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

    site_queries = {}
    for site in site_list:
        if overrides.get(site):
            site_queries[site] = overrides[site]
        else:
            query = translate_tags(tag_list, site, lookup) if tags else ""
            if query is not None:
                site_queries[site] = query
                logger.info(f"[MAP] {site}: '{query}' (from '{tags}')")

    # Fetch
    posts = await search_multi_site(
        site_queries, limit, page,
        user=user, ratios=ratio_dict, skip_interval=skip_interval,
    )

    # Post-processing
    if mappings:
        apply_reverse_mapping(posts, mappings)

    # Index raw posts BEFORE filtering (captures everything the API returns)
    background_tasks.add_task(_index_posts_task, list(posts), db)

    posts = _apply_blacklist(posts, blacklist_rules, dislikes_set)

    # Cache ALL tags from results + query tags (deduplicated)
    unique_tags = set(tag_list)
    for p in posts:
        unique_tags.update(p.get("tags", []))
    
    if unique_tags:
        background_tasks.add_task(_cache_tags_task, list(unique_tags), db)

    return {"posts": posts, "page": page, "total": len(posts), "resolved_tags": tags}


@router.get("/search")
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
    else:
        posts = await search_posts(
            site, query_str, limit, page,
            user=user, skip_interval=skip_interval,
        )
        if mappings:
            apply_reverse_mapping(posts, mappings)

    # Index raw posts BEFORE filtering (captures everything the API returns)
    if posts:
        background_tasks.add_task(_index_posts_task, list(posts), db)

    posts = _apply_blacklist(posts, blacklist_rules, dislikes_set)

    # Cache ALL tags from results + query tags (deduplicated)
    unique_tags = set(tag_list)
    for p in posts:
        unique_tags.update(p.get("tags", []))
        
    if unique_tags:
        background_tasks.add_task(_cache_tags_task, list(unique_tags), db)
    
    return {"posts": posts, "page": page, "total": len(posts), "resolved_tags": tags}


@router.get("/tags/suggest")
async def suggest_tags(
    q: str = Query(..., min_length=1, description="Tag prefix"),
    limit: int = Query(15, ge=1, le=50),
    user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    suggestions = []
    q_lower = q.lower()
    
    # 1. Provide Meta-Tag suggestions
    meta_suggests = {
        "order:": ["score", "rank", "id", "hot", "change", "favcount", "random"],
        "rating:": ["general", "sensitive", "questionable", "explicit", "g", "s", "q", "e"],
    }
    
    for prefix, values in meta_suggests.items():
        if prefix.startswith(q_lower):
            suggestions.append(prefix)
        if q_lower.startswith(prefix):
            sub_q = q_lower[len(prefix):]
            for val in values:
                if val.startswith(sub_q):
                    suggestions.append(f"{prefix}{val}")

    # 2. User's mapped tags get priority
    if user:
        mappings = await get_user_mappings(user.id, db)
        for m in mappings:
            if m.unitag.lower().startswith(q_lower) and m.unitag not in suggestions:
                suggestions.append(m.unitag)
    
    # 3. Fill remaining with global cached tags, sorted by popularity
    remaining_limit = limit - len(suggestions)
    if remaining_limit > 0:
        result = await db.execute(
            select(CachedTag)
            .where(CachedTag.tag.like(f"{q_lower}%"))
            .order_by(CachedTag.usage_count.desc())
            .limit(remaining_limit)
        )
        cached_tags = result.scalars().all()
        for ct in cached_tags:
            if ct.tag not in suggestions:
                suggestions.append(ct.tag)

    return {"suggestions": suggestions[:limit]}
