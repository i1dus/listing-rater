"""Add match_config table

Revision ID: 005
Revises: 004
Create Date: 2026-01-26

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import inspect, text

# revision identifiers, used by Alembic.
revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Проверяем, существует ли таблица
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)
    tables = inspector.get_table_names()
    
    if 'match_configs' not in tables:
        op.create_table(
            'match_configs',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('weights', postgresql.JSON(astext_type=sa.Text()), nullable=False),
            sa.Column('strict_attributes', postgresql.JSON(astext_type=sa.Text()), nullable=False),
            sa.Column('threshold', sa.String(length=10), nullable=False, server_default='70.0'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_match_configs_id'), 'match_configs', ['id'], unique=False)
    
    # Проверяем, есть ли уже данные в таблице
    result = conn.execute(sa.text("SELECT COUNT(*) FROM match_configs"))
    count = result.scalar()
    
    if count == 0:
        # Создаем начальную конфигурацию с дефолтными значениями
        op.execute("""
            INSERT INTO match_configs (is_active, weights, strict_attributes, threshold)
            VALUES (
                true,
                '{"city": 15.0, "street": 20.0, "house_number": 15.0, "rooms": 10.0, "area_total": 15.0, "floor": 5.0, "property_type": 10.0, "district": 5.0, "area_living": 3.0, "area_kitchen": 2.0}'::json,
                '["city", "street", "house_number"]'::json,
                '70.0'
            )
        """)


def downgrade() -> None:
    op.drop_index(op.f('ix_match_configs_id'), table_name='match_configs')
    op.drop_table('match_configs')
