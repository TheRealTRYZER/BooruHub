"""Add user_events and data_consent

Revision ID: 5cc68f1c9187
Revises: c61757812fdc
Create Date: 2026-03-30 22:11:53.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5cc68f1c9187'
down_revision: Union[str, None] = 'c61757812fdc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add data_consent to users (commented out because it already exists on server)
    # op.add_column('users', sa.Column('data_consent', sa.Boolean(), nullable=False, server_default='false'))
    
    # Create user_events table
    op.create_table('user_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('post_id', sa.String(length=50), nullable=True),
        sa.Column('source_site', sa.String(length=50), nullable=True),
        sa.Column('query', sa.String(length=512), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_events_event_type'), 'user_events', ['event_type'], unique=False)
    op.create_index(op.f('ix_user_events_user_id'), 'user_events', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_user_events_user_id'), table_name='user_events')
    op.drop_index(op.f('ix_user_events_event_type'), table_name='user_events')
    op.drop_table('user_events')
    op.drop_column('users', 'data_consent')
