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
    assert "score:>=250" in api_tags
    assert "order:score" in api_tags

    # If already 2 tags, should NOT inject (to keep within 2-tag limit)
    api_tags, extra = db.prepare_tags("order:score 1girl")
    assert "score:>=250" not in api_tags
    assert "order:score" in api_tags

def test_danbooru_score_floor_injection_with_rating():
    db = Danbooru()
    # If order:score is present and rating:general is enforced (making it 2 tags),
    # it should prioritize score:>=250 floor injection over rating and push rating to extra tags
    api_tags, extra = db.prepare_tags("order:score rating:general")
    assert "score:>=250" in api_tags
    assert "order:score" in api_tags
    assert "rating:general" not in api_tags
    assert "rating:general" in extra


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


@pytest.mark.asyncio
async def test_danbooru_handle_error_response_strip_auth():
    from unittest.mock import AsyncMock, MagicMock
    import httpx
    
    db = Danbooru()
    
    # Mock response and client
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 500
    
    mock_success_resp = MagicMock(spec=httpx.Response)
    mock_success_resp.status_code = 200
    
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = mock_success_resp
    
    params = {
        "tags": "order:score",
        "login": "myuser",
        "api_key": "mykey"
    }
    
    # Call handle_error_response
    res = await db.handle_error_response(
        resp=mock_resp,
        client=mock_client,
        url="https://test.com",
        params=params,
        original_tags="order:score"
    )
    
    # Assert it called client.get with stripped login/api_key
    assert res == mock_success_resp
    mock_client.get.assert_called_once()
    called_kwargs = mock_client.get.call_args[1]
    called_params = called_kwargs.get("params") or {}
    assert "login" not in called_params
    assert "api_key" not in called_params
    assert called_params["tags"] == "order:score"

