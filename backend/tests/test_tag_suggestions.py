import pytest
from httpx import AsyncClient
from unittest.mock import MagicMock

@pytest.mark.asyncio
async def test_suggest_tags_with_source(client: AsyncClient, mock_db: MagicMock):
    # Mock CachedTag objects returned by DB
    mock_tag = MagicMock()
    mock_tag.tag = "solo"
    mock_tag.usage_count = 100
    mock_tag.from_danbooru = True
    mock_tag.from_e621 = False
    mock_tag.from_rule34 = True
    
    mock_db.execute.return_value.scalars.return_value.all.return_value = [mock_tag]
    
    response = await client.get("/api/posts/tags/suggest?q=sol")
    assert response.status_code == 200
    data = response.json()
    
    # Find the "solo" suggestion
    solo_suggestion = next((s for s in data["suggestions"] if s["tag"] == "solo"), None)
    assert solo_suggestion is not None
    assert solo_suggestion["from_danbooru"] is True
    assert solo_suggestion["from_e621"] is False
    assert solo_suggestion["from_rule34"] is True
