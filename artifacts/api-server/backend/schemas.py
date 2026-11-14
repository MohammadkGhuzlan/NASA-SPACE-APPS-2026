from typing import Literal
from datetime import date
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator


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
    waterResources: str = Field(default="", max_length=1000)
    agriculturalConstraints: str = Field(default="", max_length=1000)
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


class MeasurementInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, allow_inf_nan=False, extra="forbid")
    parameter: Literal["clay_pct", "sand_pct", "silt_pct", "ph", "soc_g_kg", "soil_moisture"]
    value: float
    unit: Literal["%", "pH", "g/kg", "m3/m3", "g/100g"]
    depthTopCm: float | None = Field(default=None, ge=0, le=1000)
    depthBottomCm: float | None = Field(default=None, gt=0, le=1000)
    measuredOn: date
    source: Literal["farmer_reported", "laboratory_confirmed"]
    notes: str = Field(default="", max_length=1000)

    @model_validator(mode="after")
    def validate_measurement(self):
        bounds = {
            "clay_pct": {"%": (0, 100)}, "sand_pct": {"%": (0, 100)}, "silt_pct": {"%": (0, 100)},
            "ph": {"pH": (0, 14)}, "soc_g_kg": {"g/kg": (0, 1000), "g/100g": (0, 100)},
            "soil_moisture": {"%": (0, 100), "m3/m3": (0, 1)},
        }
        limits = bounds[self.parameter].get(self.unit)
        if limits is None or not limits[0] <= self.value <= limits[1]:
            raise ValueError("Measurement unit or physical range is invalid for this variable")
        if (self.depthTopCm is None) != (self.depthBottomCm is None):
            raise ValueError("Provide both measurement depth limits or neither")
        if self.depthTopCm is not None and self.depthBottomCm <= self.depthTopCm:
            raise ValueError("Bottom depth must exceed top depth")
        if self.parameter == "soil_moisture" and self.depthTopCm is None:
            raise ValueError("Measured soil moisture requires a depth interval")
        if self.measuredOn > date.today():
            raise ValueError("Measurement date cannot be in the future")
        return self
