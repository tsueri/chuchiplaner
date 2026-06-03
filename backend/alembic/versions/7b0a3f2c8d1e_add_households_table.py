"""add households table and user household_id / role columns

Revision ID: 7b0a3f2c8d1e
Revises: e4a17a3a7c85
Create Date: 2026-06-02 23:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '7b0a3f2c8d1e'
down_revision: Union[str, Sequence[str], None] = 'e4a17a3a7c85'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('households',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('slug', sa.String(length=255), nullable=False),
    sa.Column('invite_code', sa.String(length=32), nullable=False),
    sa.Column(
        'created_at',
        sa.DateTime(),
        server_default=sa.text('(CURRENT_TIMESTAMP)'),
        nullable=False,
    ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('slug')
    )
    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(sa.Column('household_id', sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column(
                'role',
                sa.String(length=20),
                nullable=False,
                server_default='member',
            ),
        )
        batch_op.create_foreign_key(
            'fk_users_household_id', 'households',
            ['household_id'], ['id'],
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_constraint('fk_users_household_id', type_='foreignkey')
        batch_op.drop_column('role')
        batch_op.drop_column('household_id')
    op.drop_table('households')
