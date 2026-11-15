"""Bounded, owner-scoped unvalidated inference in the normal planner."""
from concurrent.futures import ThreadPoolExecutor
import logging
import os
import re
import subprocess
import sys
import threading
import time
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from ..database import get_db
from ..recommendation.routes import owned_farm
from ..machine_learning.common import read_json, write_json, digest, now
from .models import ROOT, WARNING, manifest, crop_metadata, infer
from .operator import owner_hash
from .policy import WORKFLOW_ENABLED, INPUT_POLICY
from .inputs import public_sources

router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)
pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="experimental-ml")
lock = threading.Lock()
active = None
recent = {}


class ExperimentalInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cropCode: Literal["WHE", "BRL", "MZE", "RCD", "RCW"]
    acknowledgeWarning: Literal[True]
    retry: bool = False
    allowEstimatedInputs: bool = True


def authorized(farm):
    if WORKFLOW_ENABLED:
        return True
    if os.environ.get("NODE_ENV") != "development":
        return False
    try:
        data = read_json(ROOT / "access.json")
        return data.get("enabled") is True and (
            data.get("allDevelopmentUsers") is True or owner_hash(farm.owner) in data.get("owners", []))
    except (ValueError, OSError, TypeError):
        return False


def require_access(farm):
    if not authorized(farm):
        raise HTTPException(403, "Experimental ML requires operator-approved development access.")


def status(farm):
    access = authorized(farm)
    result = {"authorized": access, "available": False, "warning": WARNING, "models": [],
              "productionPredictionsEnabled": False, "reason": "operator_authorization_required",
              "scientificallyValidated": False}
    if access:
        try:
            data = manifest()
            result.update(available=True, models=crop_metadata(data), reason="unvalidated_predictions_enabled",
                          productionPredictionsEnabled=WORKFLOW_ENABLED)
        except (OSError, ValueError, KeyError, TypeError):
            result["reason"] = "verified_experimental_artifacts_unavailable"
    return result


def public_job(record):
    return {k: v for k, v in record.items() if k not in {"ownerHash", "farmId", "fingerprint"}}


def prune_jobs():
    # Disposable experimental cache only; never touches farms or saved reports.
    records = sorted((p for p in (ROOT / "jobs").glob("*.json")
                      if re.fullmatch(r"[0-9a-f]{64}\.json", p.name)),
                     key=lambda p: p.stat().st_mtime, reverse=True)
    for path in records[255:]:
        if path.stem != active:
            path.unlink(missing_ok=True)
            path.with_suffix(".inputs.json").unlink(missing_ok=True)


def run_job(path, record, latitude, longitude, crop):
    global active
    try:
        # Exact same scientific feature builder, not dashboard data/proxies.
        prepared_path = path.with_suffix(".inputs.json")
        subprocess.run([sys.executable, "-B", "-m", "backend.experimental.prepare",
                        "--latitude", str(latitude), "--longitude", str(longitude),
                        "--crop", crop, "--output", str(prepared_path),
                        *(["--allow-estimated-inputs"] if record.get("allowEstimatedInputs") else [])],
                       check=True, timeout=300, capture_output=True, cwd=ROOT.parents[1],
                       env={**os.environ, "PYTHONPATH": os.pathsep.join([
                            str(ROOT.parents[1] / "artifacts/api-server"), os.environ.get("PYTHONPATH", "")]),
                            "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1"})
        prep = read_json(prepared_path)
        record["inputSummary"] = {
            "selectedCoordinates": prep["selected_coordinates"],
            "labelCell": prep.get("label_cell"), "period": [2001, 2020],
            "climateSource": "NASA POWER/MERRA2",
            "climateProvenance": public_sources(prep.get("provenance", {}).get("climate")),
            "soilSource": ("ISRIC SoilGrids estimated soil inputs" if prep.get("estimated_inputs")
                           else "ISRIC SoilGrids native mean"),
            "soilDepthCm": [0, 5], "scenario": "LRLM", "compatible": prep["compatible"],
            "estimatedInputs": prep.get("estimated_inputs", False),
            "soilEstimation": prep.get("soil_estimation"),
            "originalInputRefusals": [r for r in prep.get("reasons", []) if r.startswith("ValueError:Soil_")],
            "experimentalUsable": prep.get("experimental_usable", prep["compatible"]),
            "climateRetrieved": bool(prep.get("climate_features"))}
        if not prep.get("experimental_usable", prep["compatible"]):
            reasons = prep.get("reasons", [])
            # Only explicitly safe scientific refusal details leave the server.
            safe = [r for r in reasons if r.startswith("ValueError:Soil_")]
            record.update(status="missing_inputs", reasons=["Required authentic historical climate and native soil features are incomplete.", *safe])
        else:
            request = prep["model_request"]
            output = infer(request["features"], request["latitude"], request["longitude"])
            output.setdefault("warnings", []).extend(prep.get("input_warnings", []))
            output["inputQuality"] = "estimated_soil" if prep.get("estimated_inputs") else "original_inputs"
            record.update(status="experimental_output", **output, reasons=[])
    except Exception:
        logger.exception("Experimental inference job failed; output withheld")
        record.update(status="unavailable", reasons=["Experimental artifact or input preparation failed; no prediction was fabricated."])
    finally:
        record["completedAt"] = now()
        try:
            write_json(path, record)
        finally:
            with lock:
                active = None


@router.get("/farms/{id}/experimental-ml")
def experimental_status(id: int, request: Request, db: Session = Depends(get_db)):
    return status(owned_farm(id, request, db))


@router.post("/farms/{id}/experimental-ml")
def experimental_prediction(id: int, data: ExperimentalInput, request: Request, db: Session = Depends(get_db)):
    global active
    farm = owned_farm(id, request, db)
    require_access(farm)
    if not status(farm)["available"]:
        raise HTTPException(503, "Verified experimental artifacts are unavailable; production predictions remain disabled.")
    info = manifest()
    latitude, longitude = farm.profile["latitude"], farm.profile["longitude"]
    fingerprint = digest({"farm": id, "owner": owner_hash(farm.owner), "latitude": latitude,
                           "longitude": longitude, "crop": data.cropCode, "model": info["modelVersion"],
                           "inputPolicy": INPUT_POLICY, "allowEstimatedInputs": data.allowEstimatedInputs})
    path = ROOT / "jobs" / f"{fingerprint}.json"
    with lock:
        prior = read_json(path) if path.exists() else None
        if prior and (prior["status"] != "preparing" and not data.retry):
            return public_job(prior)
        if active is not None:
            if prior and active == fingerprint:
                return public_job(prior)
            raise HTTPException(429, "Another experimental lookup is running. Please wait.")
        key = owner_hash(farm.owner)
        if time.monotonic() - recent.get(key, -1e9) < 30:
            raise HTTPException(429, "Wait 30 seconds before starting another experimental lookup.")
        # Bound the admission ledger; it contains no scientific inputs.
        if len(recent) >= 256:
            cutoff = time.monotonic()-30
            for old_key in list(recent):
                if recent[old_key] < cutoff:
                    del recent[old_key]
        recent[key] = time.monotonic()
        prune_jobs()
        record = {"jobId": fingerprint, "status": "preparing", "cropCode": data.cropCode,
                  "warning": WARNING, "value": None, "unit": "Index", "reasons": [],
                  "estimatorExecuted": False, "productionAccepted": False,
                  "inputPolicy": INPUT_POLICY, "allowEstimatedInputs": data.allowEstimatedInputs,
                  "ownerHash": key, "farmId": id, "fingerprint": fingerprint,
                  "requestedCoordinates": {"latitude": latitude, "longitude": longitude},
                  "createdAt": now()}
        write_json(path, record)
        active = fingerprint
        try:
            pool.submit(run_job, path, record.copy(), latitude, longitude, data.cropCode)
        except RuntimeError:
            active = None
            record.update(status="unavailable", reasons=["Experimental worker is unavailable. Retry after the development server is ready."])
            write_json(path, record)
    return public_job(record)


@router.get("/farms/{id}/experimental-ml/jobs/{jobId}")
def experimental_job(id: int, jobId: str, request: Request, db: Session = Depends(get_db)):
    farm = owned_farm(id, request, db)
    require_access(farm)
    if not re.fullmatch(r"[0-9a-f]{64}", jobId):
        raise HTTPException(404, "Experimental job not found.")
    try:
        record = read_json(ROOT / "jobs" / f"{jobId}.json")
    except (ValueError, OSError):
        raise HTTPException(404, "Experimental job not found.")
    if record["farmId"] != id or record["ownerHash"] != owner_hash(farm.owner):
        raise HTTPException(404, "Experimental job not found.")
    coordinates = {"latitude": farm.profile["latitude"], "longitude": farm.profile["longitude"]}
    if record["requestedCoordinates"] != coordinates:
        raise HTTPException(409, "Farm coordinates changed. Run a new experimental lookup.")
    if record["status"] == "preparing" and active != jobId:
        return {**public_job(record), "status": "interrupted",
                "reasons": ["Development server restarted. Retry explicitly to resume from cached source objects."]}
    return public_job(record)
