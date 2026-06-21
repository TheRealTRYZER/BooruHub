from unittest.mock import patch, AsyncMock
import pytest
from app.services.tag_cache import _cache_tags_task, _cache_remote_tags_task, _index_posts_task


@pytest.mark.asyncio
async def test_cache_tags_task_success():
    mock_session = AsyncMock()
    with patch("app.db.database.async_session") as mock_async_session:
        mock_async_session.return_value.__aenter__.return_value = mock_session
        
        # Call the task
        await _cache_tags_task([{"tag": "solo", "source": "danbooru"}])
        
        # Verify db.execute and commit was called
        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_cache_tags_task_retry_on_failure():
    mock_session = AsyncMock()
    # First attempt fails with Exception, second succeeds
    mock_session.execute.side_effect = [Exception("DB Error"), None]
    
    with patch("app.db.database.async_session") as mock_async_session, \
         patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        mock_async_session.return_value.__aenter__.return_value = mock_session
        
        # Call the task
        await _cache_tags_task([{"tag": "solo2", "source": "danbooru"}])
        
        # Verify db.execute was called twice
        assert mock_session.execute.call_count == 2
        mock_session.commit.assert_called_once()
        mock_sleep.assert_called_once_with(0.5)


@pytest.mark.asyncio
async def test_cache_remote_tags_task():
    mock_session = AsyncMock()
    with patch("app.db.database.async_session") as mock_async_session:
        mock_async_session.return_value.__aenter__.return_value = mock_session
        
        await _cache_remote_tags_task([{
            "tag": "cute",
            "source": "e621",
            "category": "general",
            "post_count": 500
        }])
        
        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_index_posts_task():
    mock_session = AsyncMock()
    with patch("app.db.database.async_session") as mock_async_session:
        mock_async_session.return_value.__aenter__.return_value = mock_session
        
        # Post with MD5 and post without MD5
        await _index_posts_task([
            {"id": 123, "source_site": "danbooru", "md5": "abc123abc123abc123abc123abc123ab", "tags": ["1girl"]},
            {"id": 456, "source_site": "e621", "tags": ["solo"]}
        ])
        
        # Should call execute for each batch
        assert mock_session.execute.call_count == 2
        assert mock_session.commit.call_count == 2
