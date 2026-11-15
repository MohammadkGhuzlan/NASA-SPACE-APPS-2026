"""Real development API verification; creates only isolated synthetic test farms.

Cookies stay inside the HTTP client's memory. Never overwrites existing farms.
"""
import json
from pathlib import Path
import time
from uuid import uuid4

import httpx

BASE = "http://localhost:80"
OUT = Path("generated-artifacts/experimental-ml/verification.json")
report = {"purpose": "actual API and estimator verification, not an accuracy benchmark",
          "locations": [], "productionDeployed": False}
locations = [
    ("Complete-input control", 52.876, 109.376),
    ("Irbid", 32.55696, 35.84790),
    ("Al Ain", 24.2249, 55.7452),
    ("Colusa", 39.2146, -122.0094),
    ("Stuttgart", 34.5004, -91.5526),
    ("Córdoba", 37.8882, -4.7794),
]


def save():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2))


with httpx.Client(base_url=BASE, timeout=30) as client:
    last_run = -1e9
    for index, (name, lat, lon) in enumerate(locations):
        farm = client.post("/api/farms", json={
            "name": f"Experimental check {name} {uuid4().hex[:6]}", "locationName": name,
            "latitude": lat, "longitude": lon, "currentCrop": "Maize",
            "irrigation": "rainfed", "goal": "reduce_risk", "farmSize": 10})
        farm.raise_for_status()
        farm_id = farm.json()["id"]
        if index == 0:
            initial = client.get(f"/api/farms/{farm_id}/experimental-ml")
            initial.raise_for_status()
            report["publicDevelopmentAccess"] = initial.json()["authorized"]
            assert report["publicDevelopmentAccess"], "Development access was not opened"
            save()
            deadline = time.monotonic()+1800
            while not client.get(f"/api/farms/{farm_id}/experimental-ml").json()["available"]:
                if time.monotonic() > deadline:
                    raise RuntimeError("Experimental models unavailable after bounded verification wait")
                time.sleep(10)
        time.sleep(max(0, 31-(time.monotonic()-last_run)))
        submitted = client.post(f"/api/farms/{farm_id}/experimental-ml",
            json={"cropCode": "MZE", "acknowledgeWarning": True})
        last_run = time.monotonic()
        submitted.raise_for_status()
        job = submitted.json()
        deadline = time.monotonic()+330
        while job["status"] == "preparing":
            if time.monotonic() > deadline:
                raise RuntimeError("Experimental API job exceeded its hard acquisition bound")
            time.sleep(3)
            result = client.get(f"/api/farms/{farm_id}/experimental-ml/jobs/{job['jobId']}")
            result.raise_for_status()
            job = result.json()
        # A new session can use experimental ML, but cannot access another farm.
        with httpx.Client(base_url=BASE, timeout=30) as outsider:
            ownership = outsider.get(f"/api/farms/{farm_id}/experimental-ml").status_code
        assert ownership == 404, "Public development access exposed another owner's farm"
        report["locations"].append({"name": name, "latitude": lat, "longitude": lon,
                                    "farmId": farm_id, "crossSessionStatus": ownership, "job": job})
        save()
        print(name, job["status"], job.get("value"), job.get("geographicSupport"), flush=True)
        if index == 0:
            assert job["estimatorExecuted"] and job["status"] == "experimental_output"
            assert isinstance(job["value"], (int, float))
    report["productionModelStatus"] = client.get("/api/analysis/model-status").json()
    assert report["productionModelStatus"]["predictionsEnabled"] is False
    report["completed"] = True
    save()

# Execute every authentic saved crop pipeline with re-prepared real control data.
from backend.machine_learning.farm_inputs import prepare_location
from backend.experimental.models import infer

prep = prepare_location(52.876, 109.376, "MZE", "LRLM",
                        Path("generated-artifacts/ml-recovery/environment"))
assert prep["compatible"]
request = prep["model_request"]
report["allCropControlInference"] = {}
for crop in ["BRL", "MZE", "RCD", "RCW", "WHE"]:
    features = {**request["features"], "crop": crop}
    report["allCropControlInference"][crop] = infer(features, request["latitude"], request["longitude"])
save()
