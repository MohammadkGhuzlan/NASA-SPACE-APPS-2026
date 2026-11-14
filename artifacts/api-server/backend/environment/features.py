"""Shared inference/training INPUT builder. Never emits labels or trains models."""
from .service import summary_for, soil_for
from ..models import FarmerMeasurement
from sqlalchemy import select


def build_features(db, farm, location):
    summary = summary_for(db, location)
    measurements = list(db.scalars(select(FarmerMeasurement).where(FarmerMeasurement.farm_id == farm.id).order_by(FarmerMeasurement.measured_on.desc(), FarmerMeasurement.id.desc())))
    # Keep sources separate. Only exact same 0–5 cm depth + unit + variable may
    # be used in preference to a proxy. Laboratory source remains self-reported.
    soil = soil_for(db, location)
    chosen = {}
    for parameter, unit in [("clay_pct", "%"), ("sand_pct", "%"), ("silt_pct", "%"), ("ph", "pH"), ("soc_g_kg", "g/kg")]:
        matching = next((m for m in measurements if m.parameter == parameter and m.unit == unit and m.depth_top_cm == 0 and m.depth_bottom_cm == 5), None)
        estimate = soil["estimate"]
        chosen[parameter] = {"value": matching.value if matching else estimate["properties"][parameter]["value"] if estimate else None,
            "unit": unit, "depthCm": "0-5", "source": matching.source if matching else "PROXY_DEMO_ONLY" if estimate else "unavailable",
            "measurementId": matching.id if matching else None, "groundTruthEligible": False}
    return {"farmId": farm.id, "referencePeriod": summary["referencePeriod"], "seasonal": summary["seasonal"],
        "soilInputs": chosen, "irrigation": farm.profile["irrigation"], "cropIdentity": farm.profile["currentCrop"],
        "missingValuesPreserved": True, "labels": None, "modelStatus": "not_trained",
        "warnings": ["Proxy estimates must never be ground-truth labels. Laboratory-confirmed entries are farmer-reported claims, not independently verified.", "Selected soil inputs prefer the latest measurement only for the same parameter, unit and exact 0–5 cm interval. Other depths/units remain separate."]}
