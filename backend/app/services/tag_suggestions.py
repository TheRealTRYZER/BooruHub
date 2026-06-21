"""Tag suggestions helper functions."""
import logging
from typing import Optional
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def get_similar_tags(tags_str: str, db: AsyncSession) -> Optional[str]:
    """Try to find similar tags for a search query if zero results found (optimized single query)."""
    if not tags_str:
        return None
        
    parts = tags_str.split()
    valid_parts = [p for p in parts if ":" not in p and len(p) >= 3]
    if not valid_parts:
        return None

    # O(1) single pg_trgm query for all parts
    stmt = text("""
        SELECT DISTINCT ON (part) part, tag
        FROM cached_tags, unnest(:parts) as part
        WHERE similarity(tag, part) > 0.5
        ORDER BY part, similarity(tag, part) DESC, usage_count DESC
    """)
    try:
        result = await db.execute(stmt, {"parts": valid_parts})
        matches = {row[0]: row[1] for row in result.all()}
    except Exception as e:
        logger.error(f"Error querying similar tags: {e}")
        matches = {}

    corrected = []
    changed = False
    for part in parts:
        if ":" in part or len(part) < 3:
            corrected.append(part)
            continue
        match = matches.get(part)
        if match and match != part:
            corrected.append(match)
            changed = True
        else:
            corrected.append(part)
            
    return " ".join(corrected) if changed else None
