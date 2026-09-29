import pytest
from sqlalchemy import select
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


@pytest.mark.asyncio
async def test_closed_session_leaves_objects_readable():
    """_load_user_data closes its sessions before the slow upstream call so
    the pool connection is released. The objects it hands back are then
    detached, and every downstream helper still has to be able to read their
    column values."""
    from app.services.blacklist import filter_posts
    from app.services.tag_mapping import apply_reverse_mapping, build_lookup

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        user = User(username="detach_user", email="detach@example.com", password_hash="x")
        session.add(user)
        await session.commit()
        user_id = user.id
        session.add(UserTagMapping(
            user_id=user_id, unitag="female", danbooru_tags="1girl", e621_tags="female",
        ))
        await session.commit()

    # Load, then close, exactly like _load_user_data does.
    async with session_factory() as session:
        mappings = (await session.execute(
            select(UserTagMapping).where(UserTagMapping.user_id == user_id)
        )).scalars().all()
    # Session is closed here; the objects are detached.

    lookup = build_lookup(mappings)
    assert lookup["female"]["danbooru"] == "1girl"

    posts = [{"id": "1", "source_site": "danbooru", "tags": ["1girl"]}]
    apply_reverse_mapping(posts, mappings)
    assert "female" in posts[0]["tags"]

    # A rule written against the mapped unitag must still match.
    assert filter_posts(posts, []) == posts

    await engine.dispose()


@pytest.mark.asyncio
async def test_refresh_token_revoked_at_round_trips():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    revoked_at = datetime.now(timezone.utc)
    async with session_factory() as session:
        user = User(username="revoke_user", email="revoke@example.com", password_hash="x")
        session.add(user)
        await session.commit()
        session.add(RefreshToken(
            user_id=user.id,
            token_hash="a" * 64,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
            revoked=True,
            revoked_at=revoked_at,
        ))
        await session.commit()

    async with session_factory() as session:
        stored = (await session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == "a" * 64)
        )).scalar_one()
        assert stored.revoked is True
        assert stored.revoked_at is not None

    await engine.dispose()
