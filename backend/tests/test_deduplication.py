import pytest
from app.api.posts import (
    _extract_md5_from_url,
    _extract_source_id,
    _are_duplicates,
    _merge_duplicate_posts
)

def test_extract_md5_from_url():
    # Standard URL with 32-char hex filename
    assert _extract_md5_from_url("https://api-cdn.rule34.xxx/images/4096/a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4.jpeg") == "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4"
    # Hex string inside path
    assert _extract_md5_from_url("https://cdn.donmai.us/180x180/7e/8f/7e8f5c6a1b2c3d4e5f6a1b2c3d4e5f6a.jpg") == "7e8f5c6a1b2c3d4e5f6a1b2c3d4e5f6a"
    # No md5 in URL
    assert _extract_md5_from_url("https://api-cdn.rule34.xxx/images/4096/image.png") is None

def test_extract_source_id():
    # Pixiv artwork URL
    assert _extract_source_id("https://www.pixiv.net/artworks/11223344") == "pixiv:11223344"
    assert _extract_source_id("https://www.pixiv.net/en/artworks/11223344") == "pixiv:11223344"
    # Pixiv query param URL
    assert _extract_source_id("https://www.pixiv.net/member_illust.php?mode=medium&illust_id=556677") == "pixiv:556677"
    # Direct Pixiv image URL
    assert _extract_source_id("https://i.pximg.net/img-original/img/2023/12/31/23/59/59/11223344_p0.png") == "pixiv:11223344"
    
    # Twitter status URL
    assert _extract_source_id("https://twitter.com/artist_name/status/9988776655") == "twitter:9988776655"
    assert _extract_source_id("https://x.com/artist_name/status/9988776655") == "twitter:9988776655"
    
    # Cross-site Danbooru ID
    assert _extract_source_id("https://danbooru.donmai.us/posts/777888") == "danbooru:777888"
    # Cross-site e621 ID
    assert _extract_source_id("https://e621.net/posts/666555") == "e621:666555"
    # Cross-site Rule34 ID
    assert _extract_source_id("https://rule34.xxx/index.php?page=post&s=view&id=444333") == "rule34:444333"
    
    # Unmatched
    assert _extract_source_id("https://google.com") is None

def test_are_duplicates():
    # 1. MD5 match
    post_a = {"md5": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4"}
    post_b = {"md5": "A1B2C3D4E5F6A1B2C3D4E5F6A1B2C3D4"} # case insensitive
    assert _are_duplicates(post_a, post_b) is True

    # 2. Extract MD5 from URL match
    post_c = {"file_url": "https://api-cdn.rule34.xxx/images/4096/a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4.jpeg"}
    assert _are_duplicates(post_a, post_c) is True

    # 3. Source ID match (direct Pixiv image URL vs page)
    post_d = {"source": "https://i.pximg.net/img-original/img/2023/12/31/23/59/59/11223344_p0.png"}
    post_e = {"source": "https://www.pixiv.net/member_illust.php?mode=medium&illust_id=11223344"}
    assert _are_duplicates(post_d, post_e) is True

    # 4. Exact Dimension match + sharing >= 3 tags
    post_f = {"width": 800, "height": 600, "tags": ["1girl", "solo", "long_hair", "blue_eyes"], "source_site": "danbooru"}
    post_g = {"width": 800, "height": 600, "tags": ["1girl", "solo", "long_hair", "different_tag"], "source_site": "rule34"}
    assert _are_duplicates(post_f, post_g) is True

    # 5. Exact Dimension match + less than 3 tags
    post_f2 = {"width": 800, "height": 600, "tags": ["1girl", "solo"], "source_site": "danbooru"}
    post_g2 = {"width": 800, "height": 600, "tags": ["1girl", "different_tag"], "source_site": "rule34"}
    assert _are_duplicates(post_f2, post_g2) is False

    # 6. Aspect Ratio match (resized) + sharing >= 8 tags
    post_h = {
        "width": 1600, "height": 1200, 
        "tags": ["1girl", "solo", "long_hair", "smile", "blush", "skirt", "outdoor", "scenic"],
        "source_site": "danbooru"
    }
    post_i = {
        "width": 800, "height": 600, 
        "tags": ["1girl", "solo", "long_hair", "smile", "blush", "skirt", "outdoor", "scenic", "extra_tag"],
        "source_site": "rule34"
    }
    assert _are_duplicates(post_h, post_i) is True

def test_merge_duplicate_posts():
    posts = [
        # Group 1: Danbooru (primary) and Rule34 (duplicate) via MD5
        {
            "id": "1",
            "source_site": "danbooru",
            "md5": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4",
            "score": 100,
            "width": 1000,
            "height": 1000
        },
        {
            "id": "2",
            "source_site": "rule34",
            "md5": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4",
            "score": 5,
            "width": 1000,
            "height": 1000
        },
        # Group 2: e621 (primary) and Rule34 (duplicate) via Source ID
        {
            "id": "3",
            "source_site": "e621",
            "source": "https://www.pixiv.net/artworks/9999",
            "score": 50,
            "width": 800,
            "height": 600
        },
        {
            "id": "4",
            "source_site": "rule34",
            "source": "https://www.pixiv.net/member_illust.php?mode=medium&illust_id=9999",
            "score": 10,
            "width": 800,
            "height": 600
        },
        # Group 3: Single post
        {
            "id": "5",
            "source_site": "danbooru",
            "score": 10,
            "width": 500,
            "height": 500
        }
    ]

    merged = _merge_duplicate_posts(posts)
    
    assert len(merged) == 3 # 3 unique groups
    
    # Verify Group 1 (primary should be danbooru, id "1")
    g1 = next(p for p in merged if p["id"] == "1")
    assert g1["source_site"] == "danbooru"
    assert g1["duplicate_sites"] == ["rule34"]
    assert len(g1["duplicates"]) == 1
    assert g1["duplicates"][0]["id"] == "2"

    # Verify Group 2 (primary should be e621, id "3")
    g2 = next(p for p in merged if p["id"] == "3")
    assert g2["source_site"] == "e621"
    assert g2["duplicate_sites"] == ["rule34"]
    assert len(g2["duplicates"]) == 1
    assert g2["duplicates"][0]["id"] == "4"

    # Verify Group 3 (no duplicates)
    g3 = next(p for p in merged if p["id"] == "5")
    assert "duplicates" not in g3
    assert "duplicate_sites" not in g3
