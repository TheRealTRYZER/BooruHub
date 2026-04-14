"""SQLAlchemy ORM models."""
from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime, ForeignKey, ARRAY,
    UniqueConstraint, Index, Float
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    default_tags = Column(String(255), default="")
    
    # Encrypted API keys/logins
    danbooru_login = Column(String(255), nullable=True)
    danbooru_api_key = Column(String(512), nullable=True)
    e621_login = Column(String(255), nullable=True)
    e621_api_key = Column(String(512), nullable=True)
    rule34_user_id = Column(String(255), nullable=True)
    rule34_api_key = Column(String(512), nullable=True)

    # Search preferences
    search_limit = Column(Integer, default=40)
    search_timeout = Column(Float, default=30.0)
    search_interval = Column(Float, default=0.0)

    data_consent = Column(Boolean, default=False, nullable=False, server_default='false')

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    favorites = relationship("Favorite", back_populates="user", cascade="all, delete-orphan")
    events = relationship("UserEvent", back_populates="user", cascade="all, delete-orphan")
    bookmarks = relationship("Bookmark", back_populates="user", cascade="all, delete-orphan")
    blacklist_rules = relationship("BlacklistRule", back_populates="user", cascade="all, delete-orphan")
    tag_mappings = relationship("UserTagMapping", back_populates="user", cascade="all, delete-orphan")


class UserTagMapping(Base):
    __tablename__ = "user_tag_mappings"
    __table_args__ = (
        UniqueConstraint("user_id", "unitag", name="uq_user_unitag"),
        Index("ix_mapping_user", "user_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    unitag = Column(String(255), nullable=False)
    danbooru_tags = Column(String(255), default="")
    e621_tags = Column(String(255), default="")
    rule34_tags = Column(String(255), default="")

    user = relationship("User", back_populates="tag_mappings")


class Favorite(Base):
    __tablename__ = "favorites"
    __table_args__ = (
        UniqueConstraint("user_id", "source_site", "post_id", name="uq_fav_user_post"),
        Index("ix_fav_user", "user_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    source_site = Column(String(20), nullable=False)
    post_id = Column(String(50), nullable=False)
    preview_url = Column(Text)
    file_url = Column(Text)
    sample_url = Column(Text)
    tags = Column(ARRAY(Text), default=list)
    rating = Column(String(5))
    score = Column(Integer, default=0)
    is_dislike = Column(Boolean, default=False, nullable=False, server_default='false')
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    user = relationship("User", back_populates="favorites")


class Bookmark(Base):
    __tablename__ = "bookmarks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    query = Column(Text, nullable=False)
    sites = Column(ARRAY(Text), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    user = relationship("User", back_populates="bookmarks")


class BlacklistRule(Base):
    __tablename__ = "blacklist_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    rule_line = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    user = relationship("User", back_populates="blacklist_rules")


class CachedTag(Base):
    __tablename__ = "cached_tags"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tag = Column(String(255), nullable=False, unique=True, index=True)
    usage_count = Column(Integer, default=1)
    last_seen = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )


class UserEvent(Base):
    """Tracks user interactions for the recommendation system."""
    __tablename__ = "user_events"
    __table_args__ = (
        Index("ix_events_user_ts", "user_id", "ts"),
        Index("ix_events_type_ts", "type", "ts"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    ts = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    type = Column(String(16), nullable=False)  # impression, view, like, favourite, search
    query = Column(Text, nullable=True)  # search query text
    source = Column(String(32), nullable=True)  # danbooru, e621, rule34
    post_id = Column(String(50), nullable=True)
    tags = Column(ARRAY(Text), nullable=True)  # tags at time of event (denormalized)
    duration_sec = Column(Integer, nullable=True)  # viewport time for impressions

    user = relationship("User", back_populates="events")


class PostIndex(Base):
    """Global index of all posts seen by the system."""
    __tablename__ = "post_index"
    __table_args__ = (
        UniqueConstraint("source_site", "post_id", name="uq_postindex_site_post"),
        UniqueConstraint("md5", name="uq_postindex_md5"),
        Index("ix_postindex_site", "source_site"),
        Index("ix_postindex_md5", "md5"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_site = Column(String(20), nullable=False)
    post_id = Column(String(50), nullable=False)
    md5 = Column(String(32), nullable=True)
    tags_str = Column(Text, default="")
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
