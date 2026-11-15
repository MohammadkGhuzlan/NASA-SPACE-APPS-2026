"""Closed, local, operator-created experimental bundle loader."""
from functools import lru_cache
from pathlib import Path
import math

import joblib
import numpy as np
import pandas as pd

from ..machine_learning.common import read_json, sha256
from ..machine_learning.contract import CONTRACT, CROPS, FEATURES, NUMERIC, TARGET, validate_features
from ..machine_learning.spatial import region
from ..machine_learning.training import predict, versions

ROOT = Path(__file__).resolve().parents[4] / "generated-artifacts" / "experimental-ml"
WARNING = "Experimental model — failed validation. Predictions may be inaccurate and should not be used for real farming decisions."


def manifest():
    data = read_json(ROOT / "manifest.json")
    if (data["mode"] != "experimental" or data["productionAccepted"] is not False
            or data["finalTestEvaluated"] is not False or data["contract"] != CONTRACT
            or data["target"] != TARGET or set(data["models"]) != set(CROPS)):
        raise ValueError("Experimental artifact contract mismatch")
    if data["versions"] != versions():
        raise ValueError("Experimental artifact dependency mismatch")
    return data


@lru_cache(maxsize=5)
def _load(crop, expected_hash, manifest_hash):
    path = ROOT / "models" / f"{crop}-experimental.joblib"
    if sha256(path) != expected_hash:
        raise ValueError("Experimental artifact integrity failure")
    # No upload or user path. Files must be created by the local operator CLI.
    obj = joblib.load(path)
    info = manifest()
    if (obj["crop"] != crop or obj["contract"] != CONTRACT or obj["target"] != TARGET
            or obj["datasetHash"] != info["datasetHash"] or obj["featureOrder"] != FEATURES
            or obj["productionAccepted"] is not False):
        raise ValueError("Experimental bundle identity mismatch")
    return obj


def crop_metadata(data):
    return [{"cropCode": code, "name": CROPS[code], **data["models"][code]["public"]}
            for code in sorted(data["models"])]


def infer(features, latitude, longitude):
    validate_features(features)
    crop = features["crop"]
    data = manifest()
    obj = _load(crop, data["models"][crop]["sha256"], sha256(ROOT / "manifest.json"))
    # Check the file on EVERY request, including a cached estimator.
    if sha256(ROOT / "models" / f"{crop}-experimental.joblib") != data["models"][crop]["sha256"]:
        raise ValueError("Experimental artifact integrity failure")
    value = float(predict(obj["pipeline"], pd.DataFrame([features]))[0])
    if not math.isfinite(value):
        raise ValueError("Experimental estimator returned a nonfinite output")
    coverage = obj["coverage"]
    support_reasons = []
    if region(latitude, longitude) not in obj["declaredRegions"]:
        support_reasons.append("outside_development_count_eligible_regions")
    point = np.array([features[k] for k in NUMERIC])
    training = np.array([[r[k] for k in NUMERIC] for r in coverage["training_environments"]])
    distance = float(np.linalg.norm((training-point)/np.array(coverage["scaler_scale"]), axis=1).min())
    if distance > coverage["distance_threshold"]:
        support_reasons.append("outside_development_joint_distance")
    if any(not low <= features[k] <= high for k, (low, high) in coverage["ranges"].items()):
        support_reasons.append("outside_development_feature_ranges")
    return {"value": value, "unit": "Index", "target": TARGET["meaning"],
            "modelVersion": data["modelVersion"] + "-" + crop,
            "datasetHash": data["datasetHash"], "artifactSha256": data["models"][crop]["sha256"],
            "estimatorExecuted": True, "productionAccepted": False,
            "geographicSupport": "out_of_domain" if support_reasons else "unvalidated_development_support",
            "supportReasons": support_reasons,
            "validation": data["models"][crop]["public"],
            "warnings": [WARNING, "No validated geographic domain exists, even inside the development screen.",
                         "Rain-fed low-input (LRLM), 2001–2020 historical modeled suitability; not probability, yield, profit, or rotation advice.",
                         "POWER/MERRA2 features and FAO AgERA5 labels are different climate products."]}
