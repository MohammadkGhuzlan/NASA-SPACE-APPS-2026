"""Disclosed, source-backed soil estimates; never fabricated climate or soil.

Strict research preparation is unchanged. Only this operational opt-in may use
partial native coverage, then the geographically nearest recorded TRAINING
cell's native soil means. No targets, validation errors or final-test cells
participate in proxy selection.
"""
from dataclasses import asdict
import math
from pathlib import Path
from xml.etree.ElementTree import ParseError

import httpx

from ..machine_learning.common import read_json, digest, sha256
from ..machine_learning.contract import PredictionInput, validate_features, coordinates, NUMERIC
from ..machine_learning.budget import BudgetExceeded
from ..machine_learning.environment import SOIL_PROPERTIES, native_soil_mean
from ..machine_learning.download import download
from .models import manifest, ROOT


def distance_km(a, b, c, d):
    lat1, lat2 = math.radians(a), math.radians(c)
    x = math.sin((lat2-lat1)/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(math.radians(d-b)/2)**2
    return 6371.0088 * 2 * math.asin(math.sqrt(min(1, max(0, x))))


def public_sources(value):
    if isinstance(value, dict):
        return {k: public_sources(v) for k, v in value.items() if k != "path"}
    if isinstance(value, list):
        return [public_sources(v) for v in value]
    return value


def nearest_training_soil(latitude, longitude):
    info = manifest()
    root = ROOT.parents[1]
    bundle = read_json(root / "generated-artifacts/ml-recovery/experimental-restored/dataset.json")
    checksum = bundle.pop("dataset_hash")
    if checksum != info["datasetHash"] or digest(bundle) != checksum:
        raise ValueError("Soil_proxy_dataset_integrity_failure")
    evidence_path = root / "docs/ml-recovery/evidence/expanded-evaluation.json"
    if sha256(evidence_path) != info["sourceEvaluationSha256"]:
        raise ValueError("Soil_proxy_split_evidence_integrity_failure")
    evidence = read_json(evidence_path)
    ids = {r["cell_id"] for r in evidence["splits"] if r["split"] == "train" and r["crop"] == "MZE"}
    rows = [r for r in bundle["records"] if r["crop"] == "MZE" and r["cell_id"] in ids]
    if len(rows) != len(ids) or len({r["cell_id"] for r in rows}) != len(ids) or not rows:
        raise ValueError("Soil_proxy_training_membership_mismatch")
    for row in rows:
        coordinates(row["latitude"], row["longitude"])
    row = min(rows, key=lambda r: (distance_km(latitude, longitude, r["latitude"], r["longitude"]),
                                   r["cell_id"]))
    distance = distance_km(latitude, longitude, row["latitude"], row["longitude"])
    return ({feature: row[feature] for feature in SOIL_PROPERTIES.values()},
            {"method": "nearest_recorded_training_cell", "estimated": True,
             "source": "ISRIC SoilGrids native means from verified training-feature cache",
             "sourceCoordinates": {"latitude": row["latitude"], "longitude": row["longitude"]},
             "sourceCellId": row["cell_id"], "distanceKm": distance,
             "datasetHash": checksum, "depthCm": [0, 5],
             "sourceEvidence": public_sources(row["soil_evidence"]),
             "selection": "Geographic distance only, training cells only; no target or model error used."})


def allow_soil_estimates(prepared, root, *, allow=True, budget=None):
    result = {**prepared, "experimental_usable": prepared["compatible"],
              "estimated_inputs": False, "input_warnings": []}
    if prepared["compatible"]:
        return result
    def refuse(code):
        return {**result, "model_request": None, "operational_refusal": code}
    if not prepared.get("climate_features"):
        return refuse("missing_historical_climate")
    # Validate climate independently before attempting any soil fallback. No
    # placeholder soil values are introduced, even temporarily.
    climate = prepared["climate_features"]
    climate_keys = {k for k in NUMERIC if k.startswith(("tmean_", "rain_"))}
    if (set(climate) != climate_keys or any(
            isinstance(v, bool) or not isinstance(v, (float, int)) or not math.isfinite(v)
            or not ((-100 <= v <= 70) if k.startswith("tmean_") else (0 <= v <= 100000))
            for k, v in climate.items())):
        return refuse("invalid_historical_climate")
    if not allow:
        return refuse("estimated_soil_disabled")
    cell = prepared.get("label_cell")
    if not cell:
        return refuse("unsupported_source_location")
    # Acquisition can raise HTTP errors (not OSError), or malformed/missing
    # VRT metadata errors. Both must reach the approved verified-cache path.
    source_errors = (OSError, ValueError, KeyError, TypeError, AttributeError, ParseError, httpx.HTTPError)
    try:
        soil, evidence = {}, {}
        for prop, feature in SOIL_PROPERTIES.items():
            if budget:
                budget.check()
            path = Path(root) / f"{prop}_0-5cm_mean.vrt"
            # Verify every VRT's official URL/hash, including layers the strict
            # reader never reached before its first low-coverage refusal.
            download(f"https://files.isric.org/soilgrids/latest/data/{prop}/{path.name}",
                     path, max_bytes=10_000_000)
            soil[feature], evidence[prop] = native_soil_mean(
                path, cell["latitude"], cell["longitude"], root, minimum_valid_area=.10)
        validate_features({**climate, **soil, "crop": prepared["crop"], "scenario": "LRLM"})
        provenance = {"method": "partial_native_cell_coverage", "estimated": True,
                      "source": "ISRIC SoilGrids native valid-pixel means",
                      "sourceCoordinates": {"latitude": cell["latitude"], "longitude": cell["longitude"]},
                      "sourceCellId": cell["cell_id"], "distanceKm": 0, "depthCm": [0, 5],
                      "validAreaFractions": {k: v["valid_area_fraction"] for k, v in evidence.items()},
                      "sourceEvidence": public_sources(evidence)}
        warning = ("Estimated soil inputs: native means use only available pixels (at least 10% per layer), "
                   "not the original 95%-coverage training contract. Missing portions may differ substantially.")
    except BudgetExceeded:
        return refuse("source_preparation_budget_exceeded")
    except source_errors:
        try:
            soil, provenance = nearest_training_soil(cell["latitude"], cell["longitude"])
            validate_features({**climate, **soil, "crop": prepared["crop"], "scenario": "LRLM"})
            warning = (f"Estimated soil inputs: source-cell soil means are {provenance['distanceKm']:.1f} km away, "
                       "not local farm soil. This potentially very distant proxy may be substantially inaccurate.")
        except source_errors:
            return refuse("verified_soil_proxy_unavailable_or_invalid")
    features = {**prepared["climate_features"], **soil, "crop": prepared["crop"], "scenario": "LRLM"}
    validate_features(features)
    if budget:
        try:
            budget.check()
        except BudgetExceeded:
            return refuse("source_preparation_budget_exceeded")
    request = PredictionInput(latitude=cell["latitude"], longitude=cell["longitude"], features=features)
    return {**result, "status": "prepared_with_estimated_soil", "experimental_usable": True,
            "estimated_inputs": True, "soil_estimation": provenance,
            "input_warnings": [warning, "Original training-input spatial/coverage contract is NOT satisfied. "
                              "The model and these substituted inputs are unvalidated."],
            "model_request": asdict(request)}
