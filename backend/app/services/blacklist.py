"""
Post blacklisting logic with complex operators (- for exclude, ~ for any, etc.).
"""
import re
import logging
from typing import List, Dict, Set, Optional

logger = logging.getLogger(__name__)


class BlacklistGroup:
    """A single line in the blacklist, potentially containing multiple conditions."""
    def __init__(self):
        self.include_tags: Set[str] = set()
        self.any_tags: Set[str] = set()
        self.exclude_tags: Set[str] = set()
        self.score_filter: str = ""
        self.rating_filter: str = ""

    def __bool__(self) -> bool:
        """Returns True if the group has any conditions."""
        return any([
            self.include_tags, 
            self.any_tags, 
            self.exclude_tags, 
            self.score_filter, 
            self.rating_filter
        ])


def parse_blacklist(text: str) -> List[BlacklistGroup]:
    """Parse raw blacklist text into groups of rules."""
    groups = []
    if not text:
        return groups
        
    lines = text.split('\n')
    for line in lines:
        line = line.strip().lower()
        if not line or line.startswith('#'):
            continue
        
        group = BlacklistGroup()
        tokens = line.split()
        for token in tokens:
            if token.startswith('rating:'):
                group.rating_filter = token.split(':', 1)[1]
            elif token.startswith('score:'):
                group.score_filter = token.split(':', 1)[1]
            elif token.startswith('-'):
                if len(token) > 1:
                    group.exclude_tags.add(token[1:])
            elif token.startswith('~'):
                if len(token) > 1:
                    group.any_tags.add(token[1:])
            else:
                group.include_tags.add(token)
        
        if group:
            groups.append(group)
    return groups


def _match_score(post_score: int, filter_str: str) -> bool:
    """Compare post score against a filter like '>=100'."""
    if not filter_str:
        return True
    try:
        match = re.match(r'([><=]+)(-?\d+)', filter_str)
        if match:
            op, val = match.groups()
            val = int(val)
            if op == '<': return post_score < val
            if op == '<=': return post_score <= val
            if op == '>': return post_score > val
            if op == '>=': return post_score >= val
            if op == '=': return post_score == val
    except (ValueError, TypeError, AttributeError):
        pass
    return True


def matches_rule(post: dict, group: BlacklistGroup) -> bool:
    """
    Check if a post matches a blacklist rule (and should be hidden).
    Logic:
    1. ALL include_tags must be present.
    2. AT LEAST ONE any_tags must be present (if any_tags not empty).
    3. NONE of the exclude_tags must be present.
    4. Rating and Score must match criteria.
    """
    post_tags = set(t.lower() for t in post.get("tags", []))
    raw_rating = post.get("rating", "g").lower()
    post_rating = raw_rating[0] if raw_rating else 'g'
    post_score = post.get("score", 0)

    # All include tags (ALL must match)
    if group.include_tags and not group.include_tags.issubset(post_tags):
        return False
            
    # Any tags (AT LEAST ONE must match if list not empty)
    if group.any_tags and not any(tag in post_tags for tag in group.any_tags):
        return False

    # Exclude tags (if any exclude_tag is found, the rule DOES NOT block)
    if group.exclude_tags and any(tag in post_tags for tag in group.exclude_tags):
        return False
            
    # Rating check (g, s, q, e)
    if group.rating_filter:
        if group.rating_filter[0] != post_rating:
            return False
            
    # Score comparison
    if group.score_filter and not _match_score(post_score, group.score_filter):
        return False
            
    return True


def filter_posts(posts: List[dict], groups: List[BlacklistGroup]) -> List[dict]:
    """Filter out posts that match any of the blacklist groups."""
    if not groups or not posts:
        return posts
        
    filtered = []
    for post in posts:
        is_blocked = False
        for group in groups:
            if matches_rule(post, group):
                is_blocked = True
                break
        if not is_blocked:
            filtered.append(post)
    return filtered
