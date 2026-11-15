"""Fail-closed standalone predictor. Never downloads, persists or plans rotations."""
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from .common import digest, read_json, sha256
from .contract import (
    CONTRACT, CROPS, FEATURES, NUMERIC, PERIOD, SCENARIO, TARGET, UNITS, VERSION,
    LIMITATIONS, PredictionInput, coordinates, validate_features,
)
from .spatial import block
from .training import versions, acceptance


class SuitabilityPredictor:
    """Load ONLY operator-trusted local joblib files (pickle is executable code).

    SHA-256 verifies consistency, not authorship. Do not expose model paths to users.
    """

    def __init__(self, directory: str | Path | None = None):
        self.model = None
        self.metadata = None
        self.reason = "missing_accepted_model"
        if directory is None:
            return
        root = Path(directory)
        if not (root / "accepted.joblib").is_file() or not (root / "evaluation.json").is_file():
            return
        try:
            meta = read_json(root / "evaluation.json")
            if meta["status"] != "accepted" or not meta["model_saved"] or acceptance(meta["test"], meta["config"]):
                raise ValueError("model_not_accepted")
            if (meta["contract"] != CONTRACT or meta["contract_hash"] != digest(CONTRACT) or
                    meta["target"] != TARGET or meta["versions"] != versions()):
                raise ValueError("incompatible_model_or_preprocessing")
            if sha256(root / "accepted.joblib") != meta["artifact_sha256"]:
                raise ValueError("corrupt_model_artifact")
            artifact = joblib.load(root / "accepted.joblib")
            if artifact["contract"] != CONTRACT or artifact["dataset_hash"] != meta["dataset_hash"]:
                raise ValueError("incompatible_model_or_preprocessing")
            self.model, self.metadata, self.reason = artifact["pipeline"], meta, None
        except Exception as exc:
            self.reason = str(exc) if isinstance(exc, ValueError) else "invalid_model_bundle"

    def predict(self, request: PredictionInput) -> dict:
        result = {
            "status": "unavailable", "available": False, "reasons": [],
            "crop": request.features.get("crop") if isinstance(request.features, dict) else None,
            "target": TARGET, "schema_version": VERSION, "reference_period": PERIOD,
            "source_versions": {"labels": "FAO/IIASA GAEZ v5", "climate": "NASA POWER",
                                "soil": "ISRIC SoilGrids (acquisition hashes in model manifest)"},
            "model_version": self.metadata.get("model_version") if self.metadata else None,
            "coverage_status": "not_assessed", "missing_features": [],
            "input_quality": request.source_quality, "limitations": LIMITATIONS,
        }
        if self.metadata and self.metadata.get("data_source_versions"):
            result["source_versions"] = self.metadata["data_source_versions"]

        def fail(reason, status="unsupported_input"):
            result.update(status=status, reasons=[reason])
            return result

        try:
            coordinates(request.latitude, request.longitude)
        except (ValueError, TypeError):
            return fail("invalid_coordinates")
        if not isinstance(request.features, dict):
            return fail("feature_schema_mismatch")
        if request.schema_version != VERSION or request.units != UNITS:
            return fail("feature_schema_or_units_mismatch")
        if request.period != PERIOD:
            return fail("reference_period_mismatch")
        if request.features.get("crop") not in CROPS or request.features.get("scenario") != SCENARIO:
            return fail("unsupported_crop_or_scenario")
        if (request.climate_source != "NASA POWER" or request.soil_source != "ISRIC SoilGrids" or
                request.source_quality != "verified_source_estimates"):
            return fail("required_source_unavailable_or_ineligible", "insufficient_evidence")
        if (request.soil_depth_cm != [0, 5] or request.soil_statistic != "mean" or
                request.spatial_rule != CONTRACT["spatial_rule"]):
            return fail("soil_depth_statistic_or_spatial_alignment_mismatch")
        missing = [k for k in FEATURES if k not in request.features or request.features[k] is None]
        if missing:
            result["missing_features"] = missing
            return fail("missing_required_features", "insufficient_evidence")
        try:
            validate_features(request.features)
        except (ValueError, TypeError) as exc:
            return fail(str(exc))
        if self.model is None:
            return fail(self.reason, "unavailable")
        meta = self.metadata
        if request.features["crop"] not in meta["supported_crops"] or SCENARIO not in meta["supported_scenarios"]:
            return fail("unsupported_by_model")
        support = meta["support"]
        outside = [k for k in NUMERIC if not support["ranges"][k][0] <= request.features[k] <= support["ranges"][k][1]]
        point = np.array([request.features[k] for k in NUMERIC])
        mean, scale = np.array(support["scaler_mean"]), np.array(support["scaler_scale"])
        training = np.array([[r[k] for k in NUMERIC] for r in support["training_environments"]])
        distance = float(np.linalg.norm((training-point)/scale, axis=1).min())
        result["coverage_diagnostics"] = {"outside_training_ranges": outside,
                                          "joint_standardized_distance": distance,
                                          "validated_distance_limit": support["distance_threshold"]}
        if (outside or distance > support["distance_threshold"] or
                block(request.latitude, request.longitude) not in support["heldout_blocks"]):
            result["coverage_status"] = "outside_validated_support"
            return fail("outside_validated_support", "insufficient_evidence")
        try:
            score = float(self.model.predict(pd.DataFrame([request.features], columns=FEATURES))[0])
            if not np.isfinite(score):
                raise ValueError("nonfinite_prediction")
        except Exception:
            return fail("model_execution_failed", "unavailable")
        result.update(status="supported_prediction", available=True,
                      coverage_status="limited_heldout_geography_and_environment",
                      prediction=float(np.clip(score, 0, 10000)))
        return result
