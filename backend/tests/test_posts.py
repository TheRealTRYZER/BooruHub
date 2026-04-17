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
