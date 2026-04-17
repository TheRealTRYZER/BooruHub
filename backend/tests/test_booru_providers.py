import pytest
from app.services.booru.danbooru import Danbooru

def test_danbooru_tag_preparation_empty():
    db = Danbooru()
    api_tags, extra = db.prepare_tags("")
    assert api_tags == ""
    assert extra == []

def test_danbooru_tag_preparation_limit():
    db = Danbooru()
    # Danbooru allows only 2 tags via API
    api_tags, extra = db.prepare_tags("1girl blue_eyes highres original")
    assert api_tags == "1girl blue_eyes"
    assert extra == ["highres", "original"]

def test_danbooru_score_floor_injection():
    db = Danbooru()
    # If order:score is present, we should inject a score floor to prevent 500s
    # but only if it doesn't exceed Danbooru's 2-tag limit
    api_tags, extra = db.prepare_tags("order:score")
    assert "score:>=10" in api_tags
    assert "order:score" in api_tags

    # If already 2 tags, should NOT inject (to keep within 2-tag limit)
    api_tags, extra = db.prepare_tags("order:score 1girl")
    assert "score:>=10" not in api_tags
    assert "order:score" in api_tags

def test_danbooru_normalization():
    db = Danbooru()
    raw = {
        "id": 12345,
        "tag_string": "1girl solo",
        "file_url": "https://danbooru.donmai.us/data/123.jpg",
        "large_file_url": "https://danbooru.donmai.us/sample/123.jpg",
        "rating": "s",
        "score": 100,
        "image_width": 1000,
        "image_height": 2000,
        "file_ext": "jpg",
        "md5": "abcde"
    }
    post = db.normalize_post(raw)
    assert post["id"] == "12345"
    assert post["source_site"] == "danbooru"
    assert post["rating"] == "s"
    assert post["width"] == 1000
    assert "1girl" in post["tags"]

def test_danbooru_normalization_no_url():
    db = Danbooru()
    raw = {"id": 1} # Missing file_url
    post = db.normalize_post(raw)
    assert post is None
