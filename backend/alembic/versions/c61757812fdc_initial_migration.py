"""Initial migration

Revision ID: c61757812fdc
Revises: 
Create Date: 2026-04-14 18:40:28.298276

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c61757812fdc'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Enable pg_trgm extension
    op.execute('CREATE EXTENSION IF NOT EXISTS pg_trgm')

    # 2. Table users
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('username', sa.String(length=50), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('default_tags', sa.String(length=255), server_default='', nullable=True),
        sa.Column('danbooru_login', sa.String(length=255), nullable=True),
        sa.Column('danbooru_api_key', sa.String(length=512), nullable=True),
        sa.Column('e621_login', sa.String(length=255), nullable=True),
        sa.Column('e621_api_key', sa.String(length=512), nullable=True),
        sa.Column('rule34_user_id', sa.String(length=255), nullable=True),
        sa.Column('rule34_api_key', sa.String(length=512), nullable=True),
        sa.Column('search_limit', sa.Integer(), server_default='40', nullable=True),
        sa.Column('search_timeout', sa.Float(), server_default='30.0', nullable=True),
        sa.Column('search_interval', sa.Float(), server_default='0.0', nullable=True),
        sa.Column('data_consent', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)

    # 3. Table user_tag_mappings
    op.create_table(
        'user_tag_mappings',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('unitag', sa.String(length=255), nullable=False),
        sa.Column('danbooru_tags', sa.String(length=255), server_default='', nullable=True),
        sa.Column('e621_tags', sa.String(length=255), server_default='', nullable=True),
        sa.Column('rule34_tags', sa.String(length=255), server_default='', nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'unitag', name='uq_user_unitag')
    )
    op.create_index('ix_mapping_user', 'user_tag_mappings', ['user_id'], unique=False)

    # 4. Table favorites
    op.create_table(
        'favorites',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('source_site', sa.String(length=20), nullable=False),
        sa.Column('post_id', sa.String(length=50), nullable=False),
        sa.Column('preview_url', sa.Text(), nullable=True),
        sa.Column('file_url', sa.Text(), nullable=True),
        sa.Column('sample_url', sa.Text(), nullable=True),
        sa.Column('tags', sa.ARRAY(sa.Text()), nullable=True),
        sa.Column('rating', sa.String(length=5), nullable=True),
        sa.Column('score', sa.Integer(), server_default='0', nullable=True),
        sa.Column('is_dislike', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'source_site', 'post_id', name='uq_fav_user_post')
    )
    op.create_index('ix_fav_user', 'favorites', ['user_id'], unique=False)
    op.create_index('ix_favorites_tags_gin', 'favorites', ['tags'], unique=False, postgresql_using='gin')

    # 5. Table bookmarks
    op.create_table(
        'bookmarks',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('query', sa.Text(), nullable=False),
        sa.Column('sites', sa.ARRAY(sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # 6. Table blacklist_rules
    op.create_table(
        'blacklist_rules',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('rule_line', sa.Text(), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # 7. Table cached_tags
    op.create_table(
        'cached_tags',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tag', sa.String(length=255), nullable=False),
        sa.Column('usage_count', sa.Integer(), server_default='1', nullable=True),
        sa.Column('from_danbooru', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('from_e621', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('from_rule34', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('category', sa.String(length=50), nullable=True),
        sa.Column('post_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('last_seen', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_cached_tags_tag'), 'cached_tags', ['tag'], unique=True)
    op.create_index(
        'ix_cached_tags_trgm',
        'cached_tags',
        ['tag'],
        unique=False,
        postgresql_using='gist',
        postgresql_ops={'tag': 'gist_trgm_ops'}
    )

    # 8. Table user_events
    op.create_table(
        'user_events',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('ts', sa.DateTime(timezone=True), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('type', sa.String(length=16), nullable=False),
        sa.Column('query', sa.Text(), nullable=True),
        sa.Column('source', sa.String(length=32), nullable=True),
        sa.Column('post_id', sa.String(length=50), nullable=True),
        sa.Column('tags', sa.ARRAY(sa.Text()), nullable=True),
        sa.Column('duration_sec', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_events_user_ts', 'user_events', ['user_id', 'ts'], unique=False)
    op.create_index('ix_events_type_ts', 'user_events', ['type', 'ts'], unique=False)
    op.create_index('ix_user_events_tags_gin', 'user_events', ['tags'], unique=False, postgresql_using='gin')

    # 9. Table post_index
    op.create_table(
        'post_index',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('source_site', sa.String(length=20), nullable=False),
        sa.Column('post_id', sa.String(length=50), nullable=False),
        sa.Column('md5', sa.String(length=32), nullable=True),
        sa.Column('tags_str', sa.Text(), server_default='', nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('source_site', 'post_id', name='uq_postindex_site_post'),
        sa.UniqueConstraint('md5', name='uq_postindex_md5')
    )
    op.create_index('ix_postindex_site', 'post_index', ['source_site'], unique=False)
    op.create_index('ix_postindex_md5', 'post_index', ['md5'], unique=False)

    # 10. Table refresh_tokens
    op.create_table(
        'refresh_tokens',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_refresh_tokens_token_hash'), 'refresh_tokens', ['token_hash'], unique=True)


def downgrade() -> None:
    op.drop_table('refresh_tokens')
    op.drop_table('post_index')
    op.drop_table('user_events')
    op.drop_table('cached_tags')
    op.drop_table('blacklist_rules')
    op.drop_table('bookmarks')
    op.drop_table('favorites')
    op.drop_table('user_tag_mappings')
    op.drop_table('users')
    op.execute('DROP EXTENSION IF EXISTS pg_trgm')
