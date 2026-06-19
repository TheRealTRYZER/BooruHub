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


def test_enforce_guest_rating():
    from app.api.posts import _enforce_guest_rating
    
    # 1. Normal tags -> rating:general appended
    res = _enforce_guest_rating(["1girl", "solo"])
    assert "rating:general" in res
    assert "1girl" in res
    
    # 2. Rating tag present -> stripped and replaced by rating:general
    res = _enforce_guest_rating(["1girl", "-rating:explicit", "rating:safe"])
    assert "rating:general" in res
    assert "-rating:explicit" not in res
    assert "rating:safe" not in res
    assert "1girl" in res
    
    # 3. Relationship lookup by ID -> no rating:general appended
    res = _enforce_guest_rating(["id:123"])
    assert "rating:general" not in res
    assert "id:123" in res
    
    # 4. Relationship lookup by parent -> no rating:general appended
    res = _enforce_guest_rating(["parent:456"])
    assert "rating:general" not in res
    assert "parent:456" in res


@pytest.mark.asyncio
async def test_bounded_set():
    from app.api.posts import _BoundedSet
    
    bset = _BoundedSet(maxsize=3)
    
    # Add new items
    added = await bset.add_many([1, 2])
    assert added == [1, 2]
    assert 1 in bset
    assert 2 in bset
    assert 3 not in bset
    
    # Try adding duplicates
    added = await bset.add_many([2, 3])
    assert added == [3]
    
    # Eviction should keep the most recent elements up to maxsize (B-L5)
    added = await bset.add_many([4, 5, 6, 7])
    assert len(added) == 4
    assert 1 not in bset
    assert 4 not in bset
    assert 5 in bset
    assert 6 in bset
    assert 7 in bset



