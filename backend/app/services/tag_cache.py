"""Tag and post indexing background tasks with retries and logging."""
import asyncio
import logging
from typing import List
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.bounded_set import BoundedSet
from app.db.models import CachedTag

logger = logging.getLogger(__name__)

_recently_cached_tags = BoundedSet(maxsize=10000)

async def _execute_with_retry(stmt, task_name: str) -> None:
    """Helper to execute an insert statement with up to 2 retries and exponential backoff."""
    from app.db.database import async_session
    max_retries = 2
    backoff = 0.5
    for attempt in range(max_retries + 1):
        async with async_session() as db:
            try:
                await db.execute(stmt)
                await db.commit()
                return
            except Exception as e:
                await db.rollback()
                if attempt < max_retries:
                    await asyncio.sleep(backoff * (2 ** attempt))
                else:
                    logger.error(f"[METRIC_FAILURE] Error in background task '{task_name}' after {max_retries} retries: {e}", exc_info=True)


async def _cache_tags_from_posts(posts: List[dict]) -> None:
    """Build tag_sources from already-filtered posts and queue them for caching.

    Runs as a background task so the request path never pays the cost of
    iterating every post/tag.
    """
    if not posts:
        return
    tag_sources = []
    for p in posts:
        source = p.get("source_site")
        for t in p.get("tags", []):
            tag_sources.append({"tag": t, "source": source})
    if tag_sources:
        await _cache_tags_task(tag_sources)


async def _cache_tags_task(tag_sources: List[dict]):
    """Expects tag_sources: [{"tag": "tagname", "source": "sitename"}, ...]"""
    if not tag_sources:
        return
    
    tag_map = {}
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

    # Filter out recently cached tags (thread/async-safe)
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
            from_rule34=CachedTag.from_rule34 | stmt.excluded.from_rule34,
            last_seen=func.now()
        )
    )

    await _execute_with_retry(stmt, "_cache_tags_task")


async def _cache_remote_tags_task(tag_sources: List[dict]):
    """Expects tag_sources: [{"tag": "tagname", "source": "sitename", "category": "catname", "post_count": N}, ...]"""
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
            category=func.coalesce(stmt.excluded.category, CachedTag.category),
            post_count=func.greatest(stmt.excluded.post_count, CachedTag.post_count),
            last_seen=func.now()
        )
    )

    await _execute_with_retry(stmt, "_cache_remote_tags_task")
