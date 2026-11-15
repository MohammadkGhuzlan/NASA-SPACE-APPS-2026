"""Authentic cache/source and estimator checks; never training or accuracy tests."""
import json
from pathlib import Path
import subprocess
import sys

from backend.experimental.models import infer
from backend.machine_learning.common import read_json, write_json, now

ROOT = Path("generated-artifacts/experimental-ml/estimated-checks")
SITES = [("Irbid", 32.55696, 35.84790), ("Al Ain", 24.2249, 55.7452),
         ("Colusa", 39.2146, -122.0094), ("Stuttgart", 34.5004, -91.5526),
         ("Córdoba", 37.8882, -4.7794)]


def main():
    result = {"purpose": "Operational verification using authentic climate and explicitly estimated soil; not accuracy validation.",
              "generatedAt": now(), "locations": [], "completed": False}
    for index, (name, lat, lon) in enumerate(SITES):
        path = ROOT / f"site-{index}.json"
        subprocess.run([sys.executable, "-B", "-m", "backend.experimental.prepare",
                        "--latitude", str(lat), "--longitude", str(lon), "--crop", "MZE",
                        "--output", str(path), "--allow-estimated-inputs"], timeout=300, check=True)
        prepared = read_json(path)
        item = {"name": name, "climateRetrieved": bool(prepared.get("climate_features")),
                "originalContractCompatible": prepared["compatible"],
                "usable": prepared["experimental_usable"],
                "estimatedInputs": prepared["estimated_inputs"],
                "soilEstimation": prepared.get("soil_estimation"),
                "warnings": prepared["input_warnings"]}
        if prepared["experimental_usable"]:
            request = prepared["model_request"]
            item["prediction"] = infer(request["features"], request["latitude"], request["longitude"])
        result["locations"].append(item)
        write_json(ROOT / "results.json", result)
        print(name, item["usable"], item.get("prediction", {}).get("value"),
              item.get("soilEstimation", {}).get("method"), flush=True)
    result["completed"] = True
    write_json(ROOT / "results.json", result)


if __name__ == "__main__":
    main()
