"""Add match_score field to listings

Revision ID: 004
Revises: 003
Create Date: 2026-01-26

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('listings', sa.Column('match_score', sa.Float(), nullable=True, comment='Процент сходства с объектом недвижимости (0-100)'))


def downgrade() -> None:
    op.drop_column('listings', 'match_score')
