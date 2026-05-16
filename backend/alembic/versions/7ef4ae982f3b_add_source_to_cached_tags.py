"""Add source to cached_tags

Revision ID: 7ef4ae982f3b
Revises: 6ef3ad871f2a
Create Date: 2026-05-17 00:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '7ef4ae982f3b'
down_revision: Union[str, None] = '6ef3ad871f2a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column('cached_tags', sa.Column('source', sa.String(length=50), nullable=True))

def downgrade() -> None:
    op.drop_column('cached_tags', 'source')
