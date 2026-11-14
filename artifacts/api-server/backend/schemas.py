from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator


class Polygon(BaseModel):
    type: Literal["Polygon"]
    coordinates: list[list[list[float]]]

    @field_validator("coordinates")
    @classmethod
    def valid_rings(cls, rings):
        if not rings or len(rings) > 10:
            raise ValueError("Provide between one and ten polygon rings.")
        for ring in rings:
            if len(ring) < 4 or len(ring) > 500 or ring[0] != ring[-1]:
                raise ValueError("A boundary needs three vertices and a closed ring (maximum 500 points).")
            if len({tuple(p) for p in ring[:-1]}) < 3:
                raise ValueError("A boundary needs three distinct vertices.")
            for point in ring:
                if len(point) != 2 or not -180 <= point[0] <= 180 or not -90 <= point[1] <= 90:
                    raise ValueError("Invalid boundary longitude/latitude.")
        return rings


class FarmInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, allow_inf_nan=False)
    name: str = Field(min_length=1, max_length=120)
    locationName: str = Field(min_length=1, max_length=300)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    boundary: Polygon | None = None
    currentCrop: str = Field(min_length=1, max_length=100)
    cropHistory: str = Field(default="", max_length=1000)
    irrigation: Literal["rainfed", "limited", "fully_irrigated"]
    soilType: str = Field(default="", max_length=100)
    soilMoisture: float | None = Field(default=None, ge=0, le=100)
    soilPh: float | None = Field(default=None, ge=0, le=14)
    farmSize: float | None = Field(default=None, gt=0)
    waterConstraints: str = Field(default="", max_length=1000)
    goal: Literal["conserve_water", "soil_health", "productivity", "reduce_risk"]


class StrategyInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    slot: Literal["alternative_a", "alternative_b"]
    name: str = Field(min_length=1, max_length=120)
    crops: list[str] = Field(min_length=1, max_length=6)
    notes: str = Field(default="", max_length=2000)

    @field_validator("crops")
    @classmethod
    def validate_crops(cls, crops):
        result = [c.strip() for c in crops]
        if any(not c or len(c) > 100 for c in result):
            raise ValueError("Each crop must contain 1–100 characters.")
        return result
