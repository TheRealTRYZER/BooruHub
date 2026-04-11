"""
Tag alias mapper — loads tag_aliases.csv into memory for fast lookups.
Handles resolving one tag to another based on a global alias list.
"""
import csv
import logging
from pathlib import Path
from typing import Dict, List, Set

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# In-memory alias map: antecedent -> consequent
_alias_map: Dict[str, str] = {}
# Set of all unique tags for faster search
_all_unique_tags: Set[str] = set()


def load_aliases(csv_path: Optional[str] = None) -> int:
    """Load tag aliases from CSV file into memory. Returns count loaded."""
    global _alias_map, _all_unique_tags
    
    settings = get_settings()
    path_str = csv_path or settings.TAG_ALIASES_PATH
    path = Path(path_str)
    
    if not path.exists():
        logger.warning(f"Tag aliases file not found: {path_str}")
        return 0

    count = 0
    new_map = {}
    new_unique = set()
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                status = row.get("status", "").strip().lower()
                if status != "active":
                    continue
                
                antecedent = row.get("antecedent_name", "").strip().lower().replace(" ", "_")
                consequent = row.get("consequent_name", "").strip().lower().replace(" ", "_")
                
                if antecedent and consequent:
                    new_map[antecedent] = consequent
                    new_unique.add(antecedent)
                    new_unique.add(consequent)
                    count += 1
    except Exception as e:
        logger.error(f"Failed to parse tag aliases CSV: {e}")
        return 0

    _alias_map = new_map
    _all_unique_tags = new_unique
    logger.info(f"Loaded {count} tag aliases from {path_str}")
    return count


def resolve_tag(tag: str, max_depth: int = 5) -> str:
    """Resolve a tag through alias chain. Prevents infinite loops with max_depth."""
    current = tag.strip().lower().replace(" ", "_")
    visited = {current}
    
    for _ in range(max_depth):
        if current in _alias_map:
            next_tag = _alias_map[current]
            if next_tag in visited:
                break
            current = next_tag
            visited.add(current)
        else:
            break
    return current


def resolve_tags(tags: List[str]) -> List[str]:
    """Resolve a list of tags, deduplicating the results."""
    result = []
    seen = set()
    for t in tags:
        resolved = resolve_tag(t)
        if resolved not in seen:
            seen.add(resolved)
            result.append(resolved)
    return result


def search_tags(query: str, limit: int = 20) -> List[str]:
    """Search for tags matching a query prefix."""
    q = query.strip().lower().replace(" ", "_")
    if not q:
        return []
        
    matches = [t for t in _all_unique_tags if t.startswith(q)]
    # Sort by length (shorter hits first) then alphabetically
    matches.sort(key=lambda x: (len(x), x))
    return matches[:limit]
