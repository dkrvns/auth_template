"""Add registration verification codes"""

import sqlalchemy as sa
from alembic import op


revision = '6069b9c845d0'
down_revision = '22fc503868c2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'registration_codes',
        sa.Column('email', sa.String(length=254), nullable=False),
        sa.Column('digest', sa.String(length=64), nullable=False),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('attempts_left', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('email', name=op.f('pk_registration_codes')),
    )
    op.create_index(
        op.f('ix_registration_codes_expires_at'),
        'registration_codes',
        ['expires_at'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f('ix_registration_codes_expires_at'), table_name='registration_codes'
    )
    op.drop_table('registration_codes')
