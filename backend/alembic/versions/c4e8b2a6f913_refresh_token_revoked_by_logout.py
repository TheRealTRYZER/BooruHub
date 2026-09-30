"""Mark refresh tokens revoked by an explicit logout

The reuse grace window tolerates a token that was just rotated by a second
browser tab. A logout is not a rotation, so a token revoked that way must never
be revived by the window, otherwise a captured copy of the cookie could restore
a session the user deliberately ended. The column records which revocation it
was.

Revision ID: c4e8b2a6f913
Revises: b3d9e7a1c2f4
Create Date: 2026-09-30 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4e8b2a6f913'
down_revision: Union[str, None] = 'b3d9e7a1c2f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'refresh_tokens',
        sa.Column(
            'revoked_by_logout',
            sa.Boolean(),
            nullable=False,
            server_default='false',
        ),
    )


def downgrade() -> None:
    op.drop_column('refresh_tokens', 'revoked_by_logout')
