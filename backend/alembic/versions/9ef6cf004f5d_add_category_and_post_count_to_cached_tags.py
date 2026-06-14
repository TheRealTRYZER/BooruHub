"""add category and post_count to cached_tags

Revision ID: 9ef6cf004f5d
Revises: 8ef5bf993f4c
Create Date: 2026-06-14 16:35:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '9ef6cf004f5d'
down_revision: Union[str, None] = '8ef5bf993f4c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Adding columns with fallback to existing table structure
    op.add_column('cached_tags', sa.Column('category', sa.String(length=50), nullable=True))
    op.add_column('cached_tags', sa.Column('post_count', sa.Integer(), nullable=False, server_default='0'))

def downgrade() -> None:
    op.drop_column('cached_tags', 'category')
    op.drop_column('cached_tags', 'post_count')
