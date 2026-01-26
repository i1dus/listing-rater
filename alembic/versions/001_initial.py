"""Initial migration

Revision ID: 001
Revises: 
Create Date: 2024-01-26

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create properties table
    op.create_table(
        'properties',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('city', sa.String(length=255), nullable=True),
        sa.Column('district', sa.String(length=255), nullable=True),
        sa.Column('street', sa.String(length=255), nullable=True),
        sa.Column('house_number', sa.String(length=50), nullable=True),
        sa.Column('property_type', sa.String(length=50), nullable=True),
        sa.Column('rooms', sa.Integer(), nullable=True),
        sa.Column('floor', sa.Integer(), nullable=True),
        sa.Column('floors_total', sa.Integer(), nullable=True),
        sa.Column('area_total', sa.Float(), nullable=True),
        sa.Column('area_living', sa.Float(), nullable=True),
        sa.Column('area_kitchen', sa.Float(), nullable=True),
        sa.Column('property_hash', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_properties_city'), 'properties', ['city'], unique=False)
    op.create_index(op.f('ix_properties_id'), 'properties', ['id'], unique=False)
    op.create_index(op.f('ix_properties_property_hash'), 'properties', ['property_hash'], unique=True)
    op.create_index(op.f('ix_properties_property_type'), 'properties', ['property_type'], unique=False)

    # Create listings table
    op.create_table(
        'listings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('avito_id', sa.BigInteger(), nullable=False),
        sa.Column('property_id', sa.Integer(), nullable=True),
        sa.Column('title', sa.String(length=500), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('url', sa.String(length=1000), nullable=False),
        sa.Column('deal_type', sa.String(length=50), nullable=True),
        sa.Column('price', sa.BigInteger(), nullable=True),
        sa.Column('price_per_meter', sa.Float(), nullable=True),
        sa.Column('currency', sa.String(length=10), nullable=True),
        sa.Column('city', sa.String(length=255), nullable=True),
        sa.Column('district', sa.String(length=255), nullable=True),
        sa.Column('address', sa.String(length=500), nullable=True),
        sa.Column('property_type', sa.String(length=50), nullable=True),
        sa.Column('rooms', sa.Integer(), nullable=True),
        sa.Column('floor', sa.Integer(), nullable=True),
        sa.Column('floors_total', sa.Integer(), nullable=True),
        sa.Column('area_total', sa.Float(), nullable=True),
        sa.Column('area_living', sa.Float(), nullable=True),
        sa.Column('area_kitchen', sa.Float(), nullable=True),
        sa.Column('building_type', sa.String(length=100), nullable=True),
        sa.Column('year_built', sa.Integer(), nullable=True),
        sa.Column('renovation', sa.String(length=100), nullable=True),
        sa.Column('balcony', sa.String(length=100), nullable=True),
        sa.Column('bathroom', sa.String(length=100), nullable=True),
        sa.Column('seller_name', sa.String(length=255), nullable=True),
        sa.Column('seller_type', sa.String(length=50), nullable=True),
        sa.Column('images', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('parsed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['property_id'], ['properties.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_listings_avito_id'), 'listings', ['avito_id'], unique=True)
    op.create_index(op.f('ix_listings_city'), 'listings', ['city'], unique=False)
    op.create_index(op.f('ix_listings_deal_type'), 'listings', ['deal_type'], unique=False)
    op.create_index(op.f('ix_listings_id'), 'listings', ['id'], unique=False)
    op.create_index(op.f('ix_listings_is_active'), 'listings', ['is_active'], unique=False)
    op.create_index(op.f('ix_listings_property_id'), 'listings', ['property_id'], unique=False)

    # Create status_logs table
    op.create_table(
        'status_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('listing_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('removed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('note', sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(['listing_id'], ['listings.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_status_logs_id'), 'status_logs', ['id'], unique=False)
    op.create_index(op.f('ix_status_logs_listing_id'), 'status_logs', ['listing_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_status_logs_listing_id'), table_name='status_logs')
    op.drop_index(op.f('ix_status_logs_id'), table_name='status_logs')
    op.drop_table('status_logs')
    
    op.drop_index(op.f('ix_listings_property_id'), table_name='listings')
    op.drop_index(op.f('ix_listings_is_active'), table_name='listings')
    op.drop_index(op.f('ix_listings_id'), table_name='listings')
    op.drop_index(op.f('ix_listings_deal_type'), table_name='listings')
    op.drop_index(op.f('ix_listings_city'), table_name='listings')
    op.drop_index(op.f('ix_listings_avito_id'), table_name='listings')
    op.drop_table('listings')
    
    op.drop_index(op.f('ix_properties_property_type'), table_name='properties')
    op.drop_index(op.f('ix_properties_property_hash'), table_name='properties')
    op.drop_index(op.f('ix_properties_id'), table_name='properties')
    op.drop_index(op.f('ix_properties_city'), table_name='properties')
    op.drop_table('properties')
