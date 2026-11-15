"""Normalize genuine planner evidence without disguising it as aligned ML input."""
from copy import deepcopy
from collections import OrderedDict
import hashlib
import json
import threading
import time

_cache = OrderedDict()
_cache_lock = threading.Lock()


def cached_features(farm, planning, summary, features, contract):
    """Five-minute, 64-entry process cache; all evidence participates in the key.

    Must be called only after server-side ownership validation. Changed farm
    inputs, source snapshots or contract invalidate reuse. Never caches scores.
    """
    inputs = [farm.id, farm.profile, planning.model_dump(mode="json"), summary, features, contract]
    key = hashlib.sha256(json.dumps(inputs, sort_keys=True, allow_nan=False).encode()).digest()
    now = time.monotonic()
    with _cache_lock:
        if key in _cache:
            expires, value = _cache.pop(key)
            if expires > now:
                _cache[key] = (expires, value)
                return deepcopy(value)
        result = prepare_features(farm, planning, summary, features, contract)
        _cache[key] = (now + 300, deepcopy(result))
        while len(_cache) > 64:
            _cache.popitem(last=False)
        return result


def aligned_climate_features(payload, contract):
    """Internal/offline adapter to the ACTUAL Phase 4 transform, without downloads.

    Useful for Stage B source preparation, but not proof of GAEZ spatial
    alignment and not a complete model vector. No HTTP route accepts payloads.
    """
    from ..machine_learning.contract import CONTRACT
    from ..machine_learning.environment import power_features
    if contract != CONTRACT:
        raise ValueError("unreviewed_climate_transform_contract")
    return power_features(payload, period=contract["period"])


def prepare_features(farm, planning, summary, features, contract):
    """Reusable server-only boundary. No client 'verified' assertion is accepted.

    The available point/2019–2025 features cannot meet Phase 4's 2001–2020,
    GAEZ-cell soil aggregation contract. Return diagnostic evidence, NOT zeros or
    a supposedly compatible feature vector. Stage B supplies a reviewed builder.
    """
    p = farm.profile
    reasons = []
    required_period = contract.get("period")
    if not contract:
        reasons.append("model_contract_unavailable")
    reasons.append("model_aligned_feature_builder_pending_stage_b")
    if required_period:
        expected = f"{required_period[0]}–{required_period[1]}"
        if summary.get("referencePeriod") != expected:
            reasons.append("reference_period_mismatch")
    if summary.get("status") != "available":
        reasons.append("environmental_data_incomplete")
    time_standards = sorted({
        str(x.get("metadata", {}).get("timeStandard", "unknown"))
        for x in summary.get("provenance", [])
    })
    if time_standards != [contract.get("time_standard", "UTC")]:
        reasons.append("daily_time_standard_unverified_or_mixed")
    soil = deepcopy(features.get("soilInputs", {}))
    if not soil or any(x.get("value") is None for x in soil.values()):
        reasons.append("soil_features_missing")
    # Neither farmer assertions nor nearby proxy samples establish native
    # SoilGrids area-means over the exact GAEZ label polygon.
    reasons.append("soil_source_or_spatial_aggregation_incompatible")
    irrigation = p.get("irrigation")
    # Rainfed describes water supply, not low-input management (LRLM).
    reasons.append("low_input_management_not_confirmed" if irrigation == "rainfed"
                   else "management_scenario_not_supported")
    return {
        "schemaVersion": "planner-evidence-1", "compatible": False,
        "modelFeatures": None, "requiredModelSchema": contract.get("version"),
        "requiredReferencePeriod": required_period,
        "referencePeriod": summary.get("referencePeriod"),
        "coordinates": {"latitude": p["latitude"], "longitude": p["longitude"],
                        "crs": "EPSG:4326", "farmBoundaryAggregated": False},
        "environmentStatus": summary.get("status", "unavailable"),
        "environmentRetrieval": deepcopy(summary.get("retrieval", {})),
        "environmentLocation": deepcopy(summary.get("location", {})),
        "environmentProvenance": deepcopy(summary.get("provenance", [])),
        "dailyTimeStandards": time_standards,
        "soilInputs": soil, "farmerProfile": deepcopy(p),
        "planningInputs": planning.model_dump(mode="json"),
        "unavailableReasons": reasons,
        "warnings": [
            "Farmer measurements remain self-reported, including laboratory-confirmed claims.",
            "Point climate and nearby soil proxies are not a farm-boundary aggregate.",
            "Free-text crop history and operating limits are retained, not automatically interpreted.",
            "No 2001–2020 features are made from the 2019–2025 planner data.",
        ],
    }
