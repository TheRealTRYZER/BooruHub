"""optimize_indices

Revision ID: 4d273c4d9ec8
Revises: 5cc68f1c9187
Create Date: 2026-04-17 17:32:17.396067

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4d273c4d9ec8'
down_revision: Union[str, None] = '5cc68f1c9187'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Ensure pg_trgm extension exists
    op.execute('CREATE EXTENSION IF NOT EXISTS pg_trgm')
    
    # 2. GIN index on favorites.tags (ARRAY)
    op.create_index('ix_favorites_tags_gin', 'favorites', ['tags'], unique=False, postgresql_using='gin')
    
    # 3. Add tags column if it missing (handling cases where user_events was created via older migration)
    # Using batch_alter_table for sqlite compatibility if needed, but here it's postgres
    op.add_column('user_events', sa.Column('tags', sa.ARRAY(sa.Text), nullable=True))
    
    # 4. GIN index on user_events.tags (ARRAY)
    op.create_index('ix_user_events_tags_gin', 'user_events', ['tags'], unique=False, postgresql_using='gin')
    
    # 4. GIST Trigram index on cached_tags.tag for fast similarity calls
    op.create_index(
        'ix_cached_tags_trgm', 
        'cached_tags', 
        ['tag'], 
        unique=False, 
        postgresql_using='gist', 
        postgresql_ops={'tag': 'gist_trgm_ops'}
    )


def downgrade() -> None:
    op.drop_index('ix_cached_tags_trgm', table_name='cached_tags')
    op.drop_index('ix_user_events_tags_gin', table_name='user_events')
    op.drop_index('ix_favorites_tags_gin', table_name='favorites')
