"""initial schema: vessels, positions, watchlist

Revision ID: 0001_initial
Revises:
Create Date: 2026-01-15 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "vessels",
        sa.Column("mmsi", sa.Integer(), nullable=False),
        sa.Column("imo", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=120), nullable=True),
        sa.Column("call_sign", sa.String(length=20), nullable=True),
        sa.Column("ship_type", sa.Integer(), nullable=True),
        sa.Column("flag", sa.String(length=3), nullable=True),
        sa.Column("length_m", sa.Float(), nullable=True),
        sa.Column("beam_m", sa.Float(), nullable=True),
        sa.Column("first_seen", sa.DateTime(), nullable=False),
        sa.Column("last_seen", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("mmsi"),
    )
    op.create_index("ix_vessels_imo", "vessels", ["imo"])
    op.create_index("ix_vessels_name", "vessels", ["name"])
    op.create_index("ix_vessels_last_seen", "vessels", ["last_seen"])

    op.create_table(
        "positions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("vessel_mmsi", sa.Integer(), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("sog_knots", sa.Float(), nullable=True),
        sa.Column("cog_degrees", sa.Float(), nullable=True),
        sa.Column("heading_degrees", sa.Float(), nullable=True),
        sa.Column("nav_status", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["vessel_mmsi"], ["vessels.mmsi"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_positions_mmsi_ts_desc", "positions", ["vessel_mmsi", "timestamp"])

    op.create_table(
        "watchlist",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("query", sa.String(length=120), nullable=False),
        sa.Column("submitted_at", sa.DateTime(), nullable=False),
        sa.Column("submitted_by_ip", sa.String(length=45), nullable=True),
        sa.Column("matched_mmsi", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["matched_mmsi"], ["vessels.mmsi"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("query", name="uq_watchlist_query"),
    )


def downgrade():
    op.drop_table("watchlist")
    op.drop_index("ix_positions_mmsi_ts_desc", table_name="positions")
    op.drop_table("positions")
    op.drop_index("ix_vessels_last_seen", table_name="vessels")
    op.drop_index("ix_vessels_name", table_name="vessels")
    op.drop_index("ix_vessels_imo", table_name="vessels")
    op.drop_table("vessels")
