"""Add metro fields to listings

Revision ID: 002
Revises: 001
Create Date: 2026-01-26

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('listings', sa.Column('metro', sa.String(255), nullable=True))
    op.add_column('listings', sa.Column('metro_time', sa.Integer(), nullable=True))
    op.add_column('listings', sa.Column('metro_transport', sa.String(50), nullable=True))


def downgrade() -> None:
    op.drop_column('listings', 'metro_transport')
    op.drop_column('listings', 'metro_time')
    op.drop_column('listings', 'metro')
