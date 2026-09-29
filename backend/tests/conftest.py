import os

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import ASGITransport, AsyncClient

# Must be set before app.main imports get_settings(), which is cached on first
# use. Production never sets this, so CSRF protection is always active there.
os.environ["CSRF_BYPASS_HOSTNAME"] = "test"

from app.main import app
from app.db.database import get_db

@pytest.fixture(autouse=True)
def mock_engine():
    with patch("app.main.engine") as mock:
        mock.begin.return_value.__aenter__.return_value = AsyncMock()
        yield mock

@pytest.fixture
def mock_db():
    mock = AsyncMock()
    # Use MagicMock for the result because scalars() and all() are synchronous
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock.execute.return_value = mock_result
    return mock

@pytest.fixture
async def client(mock_db):
    # Override get_db to return our mock
    async def override_get_db():
        yield mock_db
    
    app.dependency_overrides[get_db] = override_get_db
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    
    # Reset overrides after test
    app.dependency_overrides = {}
