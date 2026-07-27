"""Store post dimensions on favorites

Revision ID: 8f2a3c1d4e6b
Revises: c61757812fdc
Create Date: 2026-07-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8f2a3c1d4e6b'
down_revision: Union[str, None] = 'c61757812fdc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('favorites', sa.Column('width', sa.Integer(), nullable=True))
    op.add_column('favorites', sa.Column('height', sa.Integer(), nullable=True))
    op.add_column('favorites', sa.Column('file_ext', sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column('favorites', 'file_ext')
    op.drop_column('favorites', 'height')
    op.drop_column('favorites', 'width')
