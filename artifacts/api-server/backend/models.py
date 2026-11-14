from datetime import datetime, timezone
from sqlalchemy import String, Integer, Float, DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base


def now():
    return datetime.now(timezone.utc)


class Farm(Base):
    __tablename__ = "farms"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner: Mapped[str] = mapped_column(String(100), index=True)
    profile: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class DataSource(Base):
    __tablename__ = "data_sources"
    id: Mapped[str] = mapped_column(String(60), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    url: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50))
    description: Mapped[str] = mapped_column(Text)


class Observation(Base):
    __tablename__ = "environmental_observations"
    id: Mapped[int] = mapped_column(primary_key=True)
    farm_id: Mapped[int] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"), index=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("data_sources.id"))
    date_range: Mapped[str] = mapped_column(String(100))
    payload: Mapped[dict] = mapped_column(JSONB)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class CropDefinition(Base):
    __tablename__ = "crop_definitions"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    family: Mapped[str | None] = mapped_column(String(120))


class CropRequirement(Base):
    __tablename__ = "crop_requirements"
    id: Mapped[int] = mapped_column(primary_key=True)
    crop_id: Mapped[int] = mapped_column(ForeignKey("crop_definitions.id"))
    source_id: Mapped[str] = mapped_column(ForeignKey("data_sources.id"))
    requirements: Mapped[dict] = mapped_column(JSONB)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Strategy(Base):
    __tablename__ = "crop_rotation_strategies"
    __table_args__ = (UniqueConstraint("farm_id", "slot"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    farm_id: Mapped[int] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"), index=True)
    slot: Mapped[str] = mapped_column(String(30))
    name: Mapped[str] = mapped_column(String(120))
    crops: Mapped[list] = mapped_column(JSONB)
    notes: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40), default="unassessed_draft")


class ModelVersion(Base):
    __tablename__ = "model_versions"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    version: Mapped[str] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(40))
    metadata_json: Mapped[dict] = mapped_column(JSONB)


class RecommendationResult(Base):
    __tablename__ = "recommendation_results"
    id: Mapped[int] = mapped_column(primary_key=True)
    farm_id: Mapped[int] = mapped_column(ForeignKey("farms.id"))
    model_id: Mapped[int | None] = mapped_column(ForeignKey("model_versions.id"))
    strategy_id: Mapped[int | None] = mapped_column(ForeignKey("crop_rotation_strategies.id"))
    result: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
