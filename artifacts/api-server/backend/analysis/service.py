"""Non-invasive Phase 3 report adapter and explicit Stage A coverage refusals."""
from datetime import datetime, timezone
import logging
from .model import ADAPTER_VERSION, model_status
from .features import cached_features
from ..recommendation.knowledge import resolve

logger = logging.getLogger(__name__)
# Explicit identities from the delivered Phase 4 contract. Rice must retain its
# production type; a generic rice entry is never silently made dryland/wetland.
CROP_IDENTITIES = {"wheat": "WHE", "barley": "BRL", "maize": "MZE"}


def coverage_diagnostics(crop, prepared, status):
    code = CROP_IDENTITIES.get(resolve(crop))
    reasons = list(status["reasons"])
    if code is None:
        reasons.append("crop_not_mapped_to_reviewed_model_identity")
    reasons.extend(prepared["unavailableReasons"])
    reasons.extend(["coverage_method_not_validated_for_live_use",
                    "similar_region_estimates_disabled"])
    return {"crop": crop, "modelCrop": code, "status": "insufficient_evidence",
            "available": False, "reasons": list(dict.fromkeys(reasons))}


def integrate_report(farm, planning, summary, features, report):
    """Attach independent evidence, never rank crops or replace agronomic rules.

    Future supported outputs belong in a separate model evidence lane. No
    numeric model output is forwarded to the current reference planner.
    """
    status = model_status()
    prepared = cached_features(farm, planning, summary, features, status["contract"])
    crops = list(dict.fromkeys(
        [farm.profile["currentCrop"], *planning.currentRotation, *planning.previousCrops,
         *[c["crop"]["name"] for c in report.get("candidates", [])]]
    ))
    evidence = {
        "adapterVersion": ADAPTER_VERSION, "stage": "stage_a",
        "generatedAt": datetime.now(timezone.utc).isoformat(), "model": status,
        "featurePreparation": prepared,
        "coverage": [coverage_diagnostics(c, prepared, status) for c in crops],
        "plannerUse": "Reference rules only. No model predictions were supplied or used to rank rotations.",
        "warnings": [
            status["message"],
            ("Research candidates were fitted but did not pass geographic validation. No accepted model is active."
             if status["state"] == "insufficiently_validated" else
             "No reviewed, accepted model is active. Stage B integration remains disabled."),
            "No validated similar-region method or calibrated reliability percentage is available.",
            *prepared["warnings"],
        ],
    }
    logger.info("analysis_completed stage=stage_a prediction_available=false readiness=%s",
                status["state"])
    return {**report, "aiIntegration": evidence}
