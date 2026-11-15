from datetime import date
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator


class FarmingPlanInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, allow_inf_nan=False, extra="forbid")
    plantingDate: date | None = None
    priority: Literal["conserve_water", "soil_health", "productivity", "reduce_risk"] | None = None
    currentRotation: list[str] = Field(default_factory=list, max_length=6)
    previousCrops: list[str] = Field(default_factory=list, max_length=12)
    excludedCrops: list[str] = Field(default_factory=list, max_length=20)
    operationalLimitations: str = Field(default="", max_length=2000)
    availableSeasonalWaterMm: float | None = Field(default=None, ge=0, le=10000)

    @field_validator("currentRotation", "previousCrops", "excludedCrops")
    @classmethod
    def crop_names(cls, values):
        if any(not v.strip() or len(v.strip()) > 100 for v in values):
            raise ValueError("Crop names must contain 1–100 characters")
        return [v.strip() for v in values]

    @field_validator("plantingDate")
    @classmethod
    def planning_date(cls, value):
        if value is not None and not 2000 <= value.year <= 2100:
            raise ValueError("Use a scenario planting date between 2000 and 2100")
        return value
