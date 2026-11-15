"""Single versioned training/inference feature and scientific target contract."""
import math
from dataclasses import dataclass, field

VERSION = "gaez-approximation-1"
PERIOD = [2001, 2020]
CROPS = {"WHE": "Wheat", "BRL": "Barley", "MZE": "Maize",
         "RCD": "Dryland rice", "RCW": "Wetland rice"}
SCENARIO = "LRLM"
TARGET = {
    "meaning": "Approximation of FAO/IIASA GAEZ v5 modeled all-land suitability index",
    "unit": "Index", "range": [0, 10000], "scale_factor": 1,
    "mapset": "RES05-SXX", "period": PERIOD, "label_climate": "AgERA5",
    "not": ["observed yield", "profit", "rotation benefit", "real-time forecast"],
}
UNITS = {
    **{f"tmean_m{m:02}": "C" for m in range(1, 13)},
    **{f"rain_m{m:02}": "mm/month" for m in range(1, 13)},
    "clay_pct": "%", "sand_pct": "%", "silt_pct": "%",
    "ph": "pH", "soc_g_kg": "g/kg",
}
NUMERIC = list(UNITS)
CATEGORICAL = ["crop", "scenario"]
FEATURES = NUMERIC + CATEGORICAL
CONTRACT = {
    "version": VERSION, "numeric": NUMERIC, "categorical": CATEGORICAL,
    "units": UNITS, "period": PERIOD, "time_standard": "UTC",
    "soil_depth_cm": [0, 5], "soil_statistic": "mean",
    "missing_policy": "reject", "coordinates_as_features": False,
    "climate_source": "NASA POWER", "soil_source": "ISRIC SoilGrids",
    "spatial_rule": "GAEZ cell-center POWER point; area-mean SoilGrids over label cell",
}
LIMITATIONS = [
    "Approximates a modeled GAEZ assessment, not observed farm success.",
    "POWER and GAEZ AgERA5 are different climate products despite aligned years.",
    "Coarse regional climate and ~10 km labels do not establish field precision.",
    "0–5 cm modeled soil is not a laboratory test or a full root-zone profile.",
    "Coverage screening is conservative and is not a complete Phase 5 reliability system.",
    "No confidence percentage, yield, management benefit or rotation advice is provided.",
]


def coordinates(lat, lon):
    if isinstance(lat, bool) or isinstance(lon, bool):
        raise ValueError("invalid_coordinates")
    if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in (lat, lon)):
        raise ValueError("invalid_coordinates")
    if not -90 < lat < 90 or not -180 <= lon < 180:
        raise ValueError("invalid_coordinates")


def validate_features(values):
    if set(values) != set(FEATURES):
        raise ValueError("feature_schema_mismatch")
    if values["crop"] not in CROPS or values["scenario"] != SCENARIO:
        raise ValueError("unsupported_crop_or_scenario")
    for key in NUMERIC:
        v = values[key]
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
            raise ValueError(f"missing_or_invalid_feature:{key}")
        low, high = (-100, 70) if key.startswith("tmean") else (0, 100000)
        if key.endswith("_pct"):
            low, high = 0, 100
        elif key == "ph":
            low, high = 0, 14
        elif key == "soc_g_kg":
            low, high = 0, 1000
        if not low <= v <= high:
            raise ValueError(f"feature_out_of_range:{key}")
    if abs(sum(values[k] for k in ("clay_pct", "sand_pct", "silt_pct")) - 100) > 1:
        raise ValueError("invalid_soil_texture_sum")


@dataclass(frozen=True)
class PredictionInput:
    latitude: float
    longitude: float
    features: dict
    schema_version: str = VERSION
    period: list = field(default_factory=lambda: PERIOD.copy())
    units: dict = field(default_factory=lambda: UNITS.copy())
    climate_source: str = "NASA POWER"
    soil_source: str = "ISRIC SoilGrids"
    soil_depth_cm: list = field(default_factory=lambda: [0, 5])
    soil_statistic: str = "mean"
    spatial_rule: str = CONTRACT["spatial_rule"]
    source_quality: str = "verified_source_estimates"
