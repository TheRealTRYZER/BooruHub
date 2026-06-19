import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.db.models import Base, User, RefreshToken, UserTagMapping
from datetime import datetime, timezone, timedelta

@pytest.mark.asyncio
async def test_database_integration():
    # Use a real in-memory SQLite engine for testing SQL relationships
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        # Insert a user
        user = User(
            username="test_db_user",
            email="test_db@example.com",
            password_hash="hashed_pw",
            data_consent=True
        )
        session.add(user)
        await session.commit()
        
        assert user.id is not None
        
        # Test mapping relationship
        mapping = UserTagMapping(
            user_id=user.id,
            unitag="test_tag",
            danbooru_tags="tag1,tag2"
        )
        session.add(mapping)
        
        # Test RefreshToken relationship
        token = RefreshToken(
            user_id=user.id,
            token_hash="token_hash_value",
            expires_at=datetime.now(timezone.utc) + timedelta(days=1)
        )
        session.add(token)
        await session.commit()
        
        # Query back
        assert mapping.id is not None
        assert token.id is not None
        
    await engine.dispose()
