"""Track when a refresh token was revoked

Lets the refresh endpoint distinguish a token that was just rotated (a benign
race between two browser tabs sharing one cookie) from a real replay attempt.

Revision ID: b3d9e7a1c2f4
Revises: 8f2a3c1d4e6b
Create Date: 2026-09-29 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3d9e7a1c2f4'
down_revision: Union[str, None] = '8f2a3c1d4e6b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('refresh_tokens', sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('refresh_tokens', 'revoked_at')
