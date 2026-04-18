"""Set data_consent default to true

Revision ID: 6ef3ad871f2a
Revises: 4d273c4d9ec8
Create Date: 2026-04-18 19:52:10.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '6ef3ad871f2a'
down_revision: Union[str, None] = '4d273c4d9ec8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # 1. Change the server-side default for new rows
    op.alter_column('users', 'data_consent', server_default='true')
    
    # 2. Update all existing users to have consent by default
    op.execute("UPDATE users SET data_consent = true")

def downgrade() -> None:
    op.alter_column('users', 'data_consent', server_default='false')
