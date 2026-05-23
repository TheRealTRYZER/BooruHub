import pytest
from httpx import AsyncClient
from unittest.mock import MagicMock, AsyncMock
from app.db.models import User
from app.api.deps import get_current_user
from app.main import app

@pytest.fixture
def mock_user():
    user = User(id=42, username="testuser", email="test@test.com", data_consent=True)
    return user

@pytest.mark.asyncio
async def test_suggest_tags_with_source(client: AsyncClient, mock_db: MagicMock, mock_user):
    # Authenticate the user for the endpoint
    app.dependency_overrides[get_current_user] = lambda: mock_user

    mock_tag = MagicMock()
    mock_tag.tag = "solo"
    mock_tag.usage_count = 100
    mock_tag.from_danbooru = True
    mock_tag.from_e621 = False
    mock_tag.from_rule34 = True

    async def mock_execute(query, *args, **kwargs):
        q_str = str(query).lower()
        mock_res = MagicMock()
        if "cached_tags" in q_str:
            mock_res.scalars.return_value.all.return_value = [mock_tag]
        else:
            mock_res.scalars.return_value.all.return_value = []
        return mock_res

    mock_db.execute.side_effect = mock_execute

    response = await client.get("/api/posts/tags/suggest?q=sol")
    assert response.status_code == 200
    data = response.json()

    solo_suggestion = next((s for s in data["suggestions"] if s["tag"] == "solo"), None)
    assert solo_suggestion is not None
    assert solo_suggestion["from_danbooru"] is True
    assert solo_suggestion["from_e621"] is False
    assert solo_suggestion["from_rule34"] is True

    # Cleanup overrides
    app.dependency_overrides = {}

@pytest.mark.asyncio
async def test_suggest_tags_frequency_sorting(client: AsyncClient, mock_db: MagicMock, mock_user):
    # Authenticate the user for the endpoint
    app.dependency_overrides[get_current_user] = lambda: mock_user

    mock_solo = MagicMock()
    mock_solo.tag = "solo"
    mock_solo.usage_count = 100
    mock_solo.from_danbooru = True
    mock_solo.from_e621 = False
    mock_solo.from_rule34 = False

    mock_soldier = MagicMock()
    mock_soldier.tag = "soldier"
    mock_soldier.usage_count = 50
    mock_soldier.from_danbooru = True
    mock_soldier.from_e621 = False
    mock_soldier.from_rule34 = False

    async def mock_execute(query, *args, **kwargs):
        q_str = str(query).lower()
        mock_res = MagicMock()
        if "user_events" in q_str:
            mock_res.scalars.return_value.all.return_value = ["soldier"]
        elif "cached_tags" in q_str:
            mock_res.scalars.return_value.all.return_value = [mock_solo, mock_soldier]
        else:
            mock_res.scalars.return_value.all.return_value = []
        return mock_res

    mock_db.execute.side_effect = mock_execute

    response = await client.get("/api/posts/tags/suggest?q=sol")
    assert response.status_code == 200
    data = response.json()

    tags = [s["tag"] for s in data["suggestions"]]
    assert tags[0] == "soldier"
    assert tags[1] == "solo"

    # Cleanup overrides
    app.dependency_overrides = {}
