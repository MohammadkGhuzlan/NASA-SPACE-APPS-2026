"""Five named location checks, NOT an independent accuracy benchmark.

Uses real required-period NASA and native soil acquisition. No mock/fixture
estimator and no fake prediction ever enters these results.
"""
import argparse
from pathlib import Path
import time

from .common import write_json, now
from .contract import PredictionInput
from .farm_inputs import prepare_location
from .inference import SuitabilityPredictor

LOCATIONS = {
    "irbid": (32.55696, 35.8479),
    "al_ain": (24.2249, 55.7452),
    "colusa": (39.2146, -122.0094),
    "stuttgart": (34.5004, -91.5526),
    "cordoba": (37.8882, -4.7794),
}


def run(root, out):
    root, out = Path(root), Path(out)
    if (out / "five-locations.json").exists():
        raise ValueError("Operational evidence is immutable; use a new output directory")
    predictor = SuitabilityPredictor()  # No approved bundle exists; never load a rejected candidate.
    results = {}
    for name, (lat, lon) in LOCATIONS.items():
        started = time.monotonic()
        prepared = prepare_location(lat, lon, "WHE", "LRLM", root)
        prediction = (predictor.predict(PredictionInput(**prepared["model_request"]))
                      if prepared["compatible"] else
                      {"status": "insufficient_evidence", "available": False,
                       "reasons": prepared["reasons"]})
        results[name] = {"prepared": prepared, "prediction": prediction,
                         "estimator_executed": False, "elapsed_seconds": time.monotonic()-started}
        write_json(out / (name + ".json"), results[name])
    summary = {"generated_at": now(), "accuracy_benchmark": False, "locations": results,
               "operator_model_loaded": False, "estimator_executions": 0}
    write_json(out / "five-locations.json", summary)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", default="generated-artifacts/ml-recovery/environment")
    parser.add_argument("--out", default="generated-artifacts/ml-recovery/operational")
    args = parser.parse_args()
    run(args.cache, args.out)
