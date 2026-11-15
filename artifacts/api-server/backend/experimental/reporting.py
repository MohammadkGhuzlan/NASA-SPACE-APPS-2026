"""Immutable, owner-scoped unvalidated evidence inside new planning reports."""
from copy import deepcopy
import math
import re

from ..machine_learning.common import read_json, now
from ..recommendation.knowledge import resolve
from .models import ROOT, WARNING, manifest
from .operator import owner_hash
from .policy import INPUT_POLICY, operational_status


def snapshot_for(farm):
    latest = {}
    coordinates = {k: farm.profile[k] for k in ("latitude", "longitude")}
    try:
        info = manifest()
    except (OSError, ValueError, KeyError, TypeError):
        return {"status": "unavailable", "warning": WARNING, "jobs": [],
                "generatedAt": now(), "scope": "No verified model bundle is available."}
    for path in (ROOT / "jobs").glob("*.json"):
        if not re.fullmatch(r"[0-9a-f]{64}\.json", path.name):
            continue
        try:
            job = read_json(path)
            crop = job["cropCode"]
            if (job["farmId"] != farm.id or job["ownerHash"] != owner_hash(farm.owner)
                    or job["requestedCoordinates"] != coordinates
                    or job.get("inputPolicy") != INPUT_POLICY or crop not in info["models"]):
                continue
            if job["status"] == "experimental_output" and (
                    not job.get("estimatorExecuted") or job.get("productionAccepted") is not False
                    or isinstance(job.get("value"), bool)
                    or not isinstance(job.get("value"), (float, int)) or not math.isfinite(job["value"])
                    or job.get("artifactSha256") != info["models"][crop]["sha256"]):
                continue
            if crop not in latest or job["createdAt"] > latest[crop]["createdAt"]:
                latest[crop] = job
        except (OSError, ValueError, KeyError, TypeError):
            continue
    jobs = [{k: deepcopy(v) for k, v in j.items()
             if k not in {"farmId", "ownerHash", "fingerprint"}} for _, j in sorted(latest.items())]
    return {"status": "available_unvalidated" if any(j["status"] == "experimental_output" for j in jobs)
            else "not_requested_or_incomplete", "warning": WARNING, "jobs": jobs, "generatedAt": now(),
            "scope": "Single-crop historical suitability, not whole-rotation effects, yield, profit or calibrated confidence.",
            "plannerUse": "Unvalidated estimates accompany reference-based crop recommendations. "
                          "Agronomic rules still determine rotation alternatives; these models do not rank whole rotations."}


def attach_predictions(farm, report):
    evidence = snapshot_for(farm)
    report = {**deepcopy(report), "mlPredictions": evidence}
    status = operational_status()
    if status["predictionsEnabled"]:
        report["modelStatus"] = ("Unvalidated ML estimates included; scientific validation failed."
                                if evidence["status"] == "available_unvalidated" else
                                "Unvalidated ML enabled. Run a crop prediction before saving to include its estimate.")
    if report.get("aiIntegration"):
        old = report["aiIntegration"]
        warnings = old.get("warnings", [])
        if status["predictionsEnabled"]:
            # Preserve scientific failure warnings, not the superseded
            # Stage-A blanket assertion that no inference is available.
            warnings = [status["message"], *[w for w in warnings
                        if w != old.get("model", {}).get("message")]]
        report["aiIntegration"] = {**report["aiIntegration"], "model": status,
                                  "warnings": warnings,
                                  "plannerUse": evidence.get("plannerUse", evidence["scope"])}
    by_crop = {}
    for job in evidence["jobs"]:
        if job["status"] == "experimental_output":
            by_crop.setdefault(job["cropCode"], []).append(job)
    codes = {"wheat": ["WHE"], "barley": ["BRL"], "maize": ["MZE"], "rice": ["RCD", "RCW"]}
    for candidate in report.get("candidates", []):
        identity = resolve(candidate["crop"]["name"])
        candidate["modelEstimates"] = [deepcopy(j) for c in codes.get(identity, []) for j in by_crop.get(c, [])]
    return report
