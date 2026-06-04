import pytest
from app.main import app
from app.api.deps import get_current_user

@pytest.mark.asyncio
async def test_suggest_tags_guest(client):
    # Ensure we are testing as guest
    app.dependency_overrides[get_current_user] = lambda: None
    
    response = await client.get("/api/posts/tags/suggest?q=1girl")
    assert response.status_code == 200
    data = response.json()
    assert "suggestions" in data
    # Even with empty DB, basic structure should be there
    assert isinstance(data["suggestions"], list)
    
    # Cleanup overrides
    app.dependency_overrides = {}

@pytest.mark.asyncio
async def test_suggest_tags_meta(client):
    response = await client.get("/api/posts/tags/suggest?q=rating:")
    assert response.status_code == 200
    data = response.json()
    # Should suggest rating:general etc.
    tags = [s["tag"] for s in data["suggestions"]]
    assert "rating:general" in tags


from unittest.mock import patch, AsyncMock

@pytest.mark.asyncio
async def test_guest_mode_strips_negated_rating(client):
    # Ensure guest mode is active
    app.dependency_overrides[get_current_user] = lambda: None
    
    with patch("app.api.posts.search_posts", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = ([], 0)
        
        response = await client.get("/api/posts/search?tags=-rating:general&site=danbooru")
        assert response.status_code == 200
        
        mock_search.assert_called_once()
        called_args = mock_search.call_args[0]
        assert "rating:general" in called_args[1]
        assert "rating:safe" not in called_args[1]
        assert "-rating:general" not in called_args[1]
        
    app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_guest_mode_feed_strips_negated_rating(client):
    # Ensure guest mode is active
    app.dependency_overrides[get_current_user] = lambda: None
    
    with patch("app.api.posts.search_multi_site", new_callable=AsyncMock) as mock_search_multi:
        mock_search_multi.return_value = ([], {"danbooru": 0})
        
        response = await client.get("/api/posts/feed?tags=-rating:general&sites=danbooru")
        assert response.status_code == 200
        
        mock_search_multi.assert_called_once()
        called_args = mock_search_multi.call_args[0]
        site_queries = called_args[0]
        assert "danbooru" in site_queries
        assert site_queries["danbooru"] == "rating:general"
        
    app.dependency_overrides = {}

