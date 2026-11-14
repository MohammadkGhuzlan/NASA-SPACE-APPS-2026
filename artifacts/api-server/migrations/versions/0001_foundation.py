"""Initial Field Shift schema and source registry.

Revision ID: 0001
Revises: None
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("farms",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("owner", sa.String(100), nullable=False),
        sa.Column("profile", JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_farms_owner", "farms", ["owner"])
    sources = op.create_table("data_sources",
        sa.Column("id", sa.String(60), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("description", sa.Text, nullable=False))
    op.create_table("environmental_observations",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("farm_id", sa.Integer, sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_id", sa.String(60), sa.ForeignKey("data_sources.id"), nullable=False),
        sa.Column("date_range", sa.String(100), nullable=False),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_environmental_observations_farm_id", "environmental_observations", ["farm_id"])
    op.create_table("crop_definitions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(120), nullable=False, unique=True),
        sa.Column("family", sa.String(120)))
    op.create_table("crop_requirements",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("crop_id", sa.Integer, sa.ForeignKey("crop_definitions.id"), nullable=False),
        sa.Column("source_id", sa.String(60), sa.ForeignKey("data_sources.id"), nullable=False),
        sa.Column("requirements", JSONB, nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True)))
    op.create_table("crop_rotation_strategies",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("farm_id", sa.Integer, sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False),
        sa.Column("slot", sa.String(30), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("crops", JSONB, nullable=False),
        sa.Column("notes", sa.Text, nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.UniqueConstraint("farm_id", "slot"))
    op.create_index("ix_crop_rotation_strategies_farm_id", "crop_rotation_strategies", ["farm_id"])
    op.create_table("model_versions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("version", sa.String(60), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("metadata_json", JSONB, nullable=False))
    op.create_table("recommendation_results",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("farm_id", sa.Integer, sa.ForeignKey("farms.id"), nullable=False),
        sa.Column("model_id", sa.Integer, sa.ForeignKey("model_versions.id")),
        sa.Column("strategy_id", sa.Integer, sa.ForeignKey("crop_rotation_strategies.id")),
        sa.Column("result", JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.bulk_insert(sources, [
        {"id": "nasa_power", "name": "NASA POWER", "url": "https://power.larc.nasa.gov/", "status": "connected_on_demand", "description": "Daily T2M (°C), T2M_MAX (°C), PRECTOTCORR (mm/day), aggregated for 2025. Gridded estimates, not field measurements. Retrieval failures produce explicit missing-data states."},
        {"id": "openstreetmap", "name": "OpenStreetMap / Nominatim", "url": "https://www.openstreetmap.org/copyright", "status": "connected", "description": "Global basemap and place search. © OpenStreetMap contributors. Search via Nominatim, maximum one upstream request per second. Not an environmental observation source."},
        {"id": "farmer", "name": "Farmer-provided information", "url": "", "status": "user_provided", "description": "Unverified user entries. Soil moisture is volumetric water content (%), farm size is hectares, pH is dimensionless. No satellite measurement is inferred from these entries."},
        {"id": "nasa_smap", "name": "NASA SMAP soil moisture", "url": "https://smap.jpl.nasa.gov/", "status": "not_connected", "description": "Planned soil moisture integration. No SMAP measurements are displayed."},
        {"id": "nasa_modis", "name": "NASA MODIS vegetation", "url": "https://modis.gsfc.nasa.gov/", "status": "not_connected", "description": "Planned vegetation integration. No vegetation index or crop-health score is inferred."},
        {"id": "crop_requirements", "name": "Verified crop requirements", "url": "https://www.fao.org/land-water/databases-and-software/crop-information/en/", "status": "not_imported", "description": "Reference for future curation, not an imported dataset. Crop definitions, requirements, rotation rules and trained models remain empty; drafts are not recommendations."},
    ])


def downgrade():
    raise RuntimeError("Destructive downgrade is disabled. Use a reviewed database restore procedure.")
