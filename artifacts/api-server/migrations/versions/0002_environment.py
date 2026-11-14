"""Additive environmental data, provenance and ingestion reporting.

Frozen schema: deliberately does not import current application ORM definitions.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("environment_locations",
        sa.Column("key", sa.String(60), primary_key=True),
        sa.Column("latitude", sa.Float, nullable=False),
        sa.Column("longitude", sa.Float, nullable=False),
        sa.Column("study_id", sa.String(30), unique=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("metadata_json", JSONB, nullable=False),
        sa.Column("last_attempt", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.Text))
    op.create_table("environment_values",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("location_key", sa.String(60), sa.ForeignKey("environment_locations.key"), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("parameter", sa.String(30), nullable=False),
        sa.Column("value", sa.Float),
        sa.Column("unit", sa.String(30), nullable=False),
        sa.Column("source", sa.String(100), nullable=False),
        sa.Column("product", sa.String(100), nullable=False),
        sa.Column("source_url", sa.Text, nullable=False),
        sa.Column("classification", sa.String(100), nullable=False),
        sa.Column("quality", sa.String(50), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata_json", JSONB, nullable=False),
        sa.UniqueConstraint("location_key", "date", "parameter", "product"))
    op.create_index("ix_environment_values_location_key", "environment_values", ["location_key"])
    op.create_index("ix_environment_values_date", "environment_values", ["date"])
    op.create_table("soil_property_estimates",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("location_key", sa.String(60), sa.ForeignKey("environment_locations.key"), unique=True, nullable=False),
        sa.Column("original_latitude", sa.Float, nullable=False),
        sa.Column("original_longitude", sa.Float, nullable=False),
        sa.Column("sample_latitude", sa.Float, nullable=False),
        sa.Column("sample_longitude", sa.Float, nullable=False),
        sa.Column("offset_km", sa.Float, nullable=False),
        sa.Column("depth_cm", sa.String(30), nullable=False),
        sa.Column("classification", sa.String(100), nullable=False),
        sa.Column("properties", JSONB, nullable=False),
        sa.Column("provenance", JSONB, nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("farmer_measurements",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("farm_id", sa.Integer, sa.ForeignKey("farms.id"), nullable=False),
        sa.Column("parameter", sa.String(40), nullable=False),
        sa.Column("value", sa.Float, nullable=False),
        sa.Column("unit", sa.String(30), nullable=False),
        sa.Column("depth_top_cm", sa.Float),
        sa.Column("depth_bottom_cm", sa.Float),
        sa.Column("measured_on", sa.Date, nullable=False),
        sa.Column("source", sa.String(40), nullable=False),
        sa.Column("notes", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_farmer_measurements_farm_id", "farmer_measurements", ["farm_id"])
    op.create_table("ingestion_reports",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("source", sa.String(300), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("report", JSONB, nullable=False))


def downgrade():
    raise RuntimeError("Destructive downgrade disabled; use a reviewed restore.")
