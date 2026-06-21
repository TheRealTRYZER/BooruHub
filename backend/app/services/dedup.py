"""Deduplication logic for post results."""
import logging
import re
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


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

    # 1. Compare MD5s (using cached precomputed values or fallback)
    md5_a = a.get("_extracted_md5") or a.get("md5") or _extract_md5_from_url(a.get("file_url") or "")
    md5_b = b.get("_extracted_md5") or b.get("md5") or _extract_md5_from_url(b.get("file_url") or "")
    if md5_a and md5_b and md5_a.lower() == md5_b.lower():
        return True

    # 2. Compare Source IDs
    src_a = a.get("source") or ""
    src_b = b.get("source") or ""
    if src_a and src_b:
        id_a = _extract_source_id(src_a)
        id_b = _extract_source_id(src_b)
        if id_a and id_b and id_a == id_b:
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
        ratio_a = a.get("_aspect_ratio") or (w_a / h_a if h_a else None)
        ratio_b = b.get("_aspect_ratio") or (w_b / h_b if h_b else None)
        if ratio_a and ratio_b and abs(ratio_a - ratio_b) / max(ratio_a, ratio_b) < 0.005:
            tags_a = set(a.get("tags", []))
            tags_b = set(b.get("tags", []))
            intersection = tags_a & tags_b
            if tags_a and len(intersection) / len(tags_a | tags_b) >= 0.60:
                return True

    return False


def _merge_duplicate_posts(posts: List[dict]) -> List[dict]:
    """Group/merge duplicate posts together using O(1) dict lookups for MD5 and Source ID, and bucketed aspect ratio checks."""
    if not posts:
        return []

    # Precompute aspect ratio and extracted MD5 for caching (B-M6)
    for post in posts:
        if "_aspect_ratio" not in post:
            w, h = post.get("width"), post.get("height")
            post["_aspect_ratio"] = w / h if w and h else None
        if "_extracted_md5" not in post:
            post["_extracted_md5"] = (post.get("md5") or "").strip().lower() or _extract_md5_from_url(post.get("file_url") or "") or _extract_md5_from_url(post.get("sample_url") or "")

    groups: List[List[dict]] = []
    md5_groups = {}
    source_groups = {}
    
    # Buckets for O(1) dimension and aspect ratio lookups (B-M6)
    dimension_buckets: Dict[tuple, List[List[dict]]] = {}
    aspect_ratio_buckets: List[Tuple[float, List[dict]]] = []

    for post in posts:
        matched_group = None
        
        # 1. Try matching by MD5
        md5 = post["_extracted_md5"]
        if md5:
            matched_group = md5_groups.get(md5)
            
        # 2. Try matching by Source ID
        if not matched_group:
            src = post.get("source") or ""
            source_id = _extract_source_id(src) if src else None
            if source_id:
                matched_group = source_groups.get(source_id)
                if matched_group:
                    tags_a = set(post.get("tags", []))
                    tags_b = set(matched_group[0].get("tags", []))
                    if tags_a and tags_b:
                        intersection = tags_a & tags_b
                        if len(intersection) / len(tags_a | tags_b) < 0.60:
                            matched_group = None

        # 3. Fallback to pre-bucketed dimension and aspect ratio matches
        if not matched_group:
            w, h = post.get("width"), post.get("height")
            if w and h and w > 100 and h > 100:
                dim_key = (w, h)
                for g in dimension_buckets.get(dim_key, []):
                    tags_a = set(post.get("tags", []))
                    tags_b = set(g[0].get("tags", []))
                    if tags_a and tags_b:
                        intersection = tags_a & tags_b
                        if len(intersection) / len(tags_a | tags_b) >= 0.60:
                            matched_group = g
                            break
                            
                if not matched_group:
                    ratio = post["_aspect_ratio"]
                    if ratio:
                        for r, g in aspect_ratio_buckets:
                            if abs(ratio - r) / max(ratio, r) < 0.005:
                                tags_a = set(post.get("tags", []))
                                tags_b = set(g[0].get("tags", []))
                                if tags_a and tags_b:
                                    intersection = tags_a & tags_b
                                    if len(intersection) / len(tags_a | tags_b) >= 0.60:
                                        matched_group = g
                                        break

        # 4. Group or insert
        if matched_group is not None:
            # Don't merge duplicates from the same site
            if not any(p.get("source_site") == post.get("source_site") for p in matched_group):
                matched_group.append(post)
                if md5:
                    md5_groups[md5] = matched_group
                src = post.get("source") or ""
                source_id = _extract_source_id(src) if src else None
                if source_id:
                    source_groups[source_id] = matched_group
        else:
            new_group = [post]
            groups.append(new_group)
            if md5:
                md5_groups[md5] = new_group
            src = post.get("source") or ""
            source_id = _extract_source_id(src) if src else None
            if source_id:
                source_groups[source_id] = new_group
                
            # Add to dimension and aspect ratio buckets
            w, h = post.get("width"), post.get("height")
            if w and h and w > 100 and h > 100:
                dim_key = (w, h)
                if dim_key not in dimension_buckets:
                    dimension_buckets[dim_key] = []
                dimension_buckets[dim_key].append(new_group)
                
                ratio = post["_aspect_ratio"]
                if ratio:
                    aspect_ratio_buckets.append((ratio, new_group))

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
