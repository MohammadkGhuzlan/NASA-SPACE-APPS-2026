"""Read only application-controlled JSON contracts. Stage A never unpickles.

Do not add a client model-path parameter or a joblib.load call here. Activation
requires a separate Stage B review, a trusted bundle and independent validation.
"""
from copy import deepcopy
from functools import lru_cache
import json
from pathlib import Path

ADAPTER_VERSION = "field-shift-analysis-1"
EVIDENCE = Path(__file__).resolve().parents[4] / "docs/phase4/evidence"
MESSAGE = "AI crop-suitability predictions are not yet available."


def readiness(contract, evidence, target):
    """Pure classifier; even an accepted research report cannot activate Stage A."""
    state, reasons = "not_installed", ["missing_accepted_model"]
    required = {"version", "period", "numeric", "categorical", "units", "spatial_rule",
                "soil_source", "soil_depth_cm", "soil_statistic", "time_standard"}
    if not isinstance(contract, dict) or not required.issubset(contract):
        state, reasons, contract = "incompatible", ["invalid_feature_contract"], {}
    elif (not isinstance(contract["period"], list) or len(contract["period"]) != 2
          or not isinstance(contract["numeric"], list) or not contract["numeric"]
          or not isinstance(contract["units"], dict)
          or set(contract["numeric"]) != set(contract["units"])):
        state, reasons, contract = "incompatible", ["invalid_feature_contract"], {}
    elif not isinstance(evidence, dict):
        state, reasons = "temporarily_unavailable", ["invalid_validation_evidence"]
    elif evidence.get("outcome") in {"rejected", "rejected_on_validation", "insufficient_evidence"}:
        state, reasons = "insufficiently_validated", ["phase4_validation_not_passed", "missing_accepted_model"]
    elif evidence.get("deployable_model_saved") or evidence.get("outcome") == "accepted":
        state, reasons = "incompatible", ["stage_b_operator_review_required"]
    return {
        "adapterVersion": ADAPTER_VERSION, "stage": "stage_a", "state": state,
        "predictionsEnabled": False, "message": MESSAGE, "reasons": reasons,
        "contract": deepcopy(contract), "target": deepcopy(target) if isinstance(target, dict) else {},
    }


@lru_cache(maxsize=1)
def _status():
    try:
        contract = json.loads((EVIDENCE / "feature-contract.json").read_text())
        evidence = json.loads((EVIDENCE / "run-summary.json").read_text())
        example = json.loads((EVIDENCE / "example-response.json").read_text())
        # This is contract metadata only. The example's score/availability is
        # deliberately not read as a real model prediction.
        return readiness(contract, evidence, example.get("target"))
    except (OSError, ValueError, TypeError, AttributeError):
        return {
            "adapterVersion": ADAPTER_VERSION, "stage": "stage_a",
            "state": "temporarily_unavailable", "predictionsEnabled": False,
            "message": MESSAGE, "reasons": ["model_metadata_unavailable"],
            "contract": {}, "target": {},
        }


def model_status():
    # No caller may mutate cached metadata. Restart to pick up reviewed changes.
    return deepcopy(_status())
