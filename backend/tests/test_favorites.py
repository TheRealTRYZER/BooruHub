import pytest
from unittest.mock import MagicMock
from app.main import app
from app.api.deps import require_user
from app.db.models import User, Favorite

@pytest.mark.asyncio
async def test_list_favorites_returns_is_dislike(client, mock_db):
    dummy_user = User(id=1, username="testuser", email="test@test.com")
    app.dependency_overrides[require_user] = lambda: dummy_user

    mock_count_result = MagicMock()
    mock_count_result.scalar.return_value = 1

    mock_fav = Favorite(
        id=123,
        user_id=1,
        source_site="danbooru",
        post_id="999",
        preview_url="https://test.com/prev.jpg",
        file_url="https://test.com/file.jpg",
        sample_url="https://test.com/sample.jpg",
        tags=["1girl", "solo"],
        rating="g",
        score=100,
        is_dislike=True
    )
    mock_favs_result = MagicMock()
    mock_favs_result.scalars.return_value.all.return_value = [mock_fav]

    mock_db.execute.side_effect = [mock_count_result, mock_favs_result]

    response = await client.get("/api/favorites?is_dislike=true")
    assert response.status_code == 200
    data = response.json()
    assert "favorites" in data
    assert len(data["favorites"]) == 1
    fav = data["favorites"][0]
    assert fav["id"] == 123
    assert fav["is_dislike"] is True

    app.dependency_overrides = {}
