from unittest.mock import MagicMock, AsyncMock
import pytest
from app.services.tag_suggestions import get_similar_tags


@pytest.mark.asyncio
async def test_get_similar_tags_correction():
    mock_db = AsyncMock()
    # Mock result with matching values
    mock_result = MagicMock()
    mock_result.all.return_value = [("1gir", "1girl")]
    mock_db.execute.return_value = mock_result
    
    res = await get_similar_tags("1gir solo", mock_db)
    assert res == "1girl solo"
    mock_db.execute.assert_called_once()


@pytest.mark.asyncio
async def test_get_similar_tags_no_correction():
    mock_db = AsyncMock()
    # If same tag returned
    mock_result = MagicMock()
    mock_result.all.return_value = [("1girl", "1girl")]
    mock_db.execute.return_value = mock_result
    
    res = await get_similar_tags("1girl solo", mock_db)
    assert res is None
