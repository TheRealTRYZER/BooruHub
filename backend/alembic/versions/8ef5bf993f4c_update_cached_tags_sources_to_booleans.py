"""Update cached_tags sources to booleans

Revision ID: 8ef5bf993f4c
Revises: 7ef4ae982f3b
Create Date: 2026-05-17 00:40:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '8ef5bf993f4c'
down_revision: Union[str, None] = '7ef4ae982f3b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # 1. Add new columns
    op.add_column('cached_tags', sa.Column('from_danbooru', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('cached_tags', sa.Column('from_e621', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('cached_tags', sa.Column('from_rule34', sa.Boolean(), nullable=False, server_default='false'))
    
    # 2. Try to migrate data from 'source' column if it exists
    # We can use simple UPDATEs
    op.execute("UPDATE cached_tags SET from_danbooru = true WHERE source = 'danbooru'")
    op.execute("UPDATE cached_tags SET from_e621 = true WHERE source = 'e621'")
    op.execute("UPDATE cached_tags SET from_rule34 = true WHERE source = 'rule34'")
    
    # 3. Drop old column
    op.drop_column('cached_tags', 'source')

def downgrade() -> None:
    op.add_column('cached_tags', sa.Column('source', sa.String(length=50), nullable=True))
    op.execute("UPDATE cached_tags SET source = 'danbooru' WHERE from_danbooru = true")
    op.execute("UPDATE cached_tags SET source = 'e621' WHERE from_e621 = true AND from_danbooru = false")
    op.execute("UPDATE cached_tags SET source = 'rule34' WHERE from_rule34 = true AND from_danbooru = false AND from_e621 = false")
    op.drop_column('cached_tags', 'from_danbooru')
    op.drop_column('cached_tags', 'from_e621')
    op.drop_column('cached_tags', 'from_rule34')
