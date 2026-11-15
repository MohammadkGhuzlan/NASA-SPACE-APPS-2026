"""Local operator CLI. No HTTP interface can grant experimental privileges."""
import argparse
import hashlib
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import RandomForestRegressor

from .models import ROOT
from ..machine_learning.common import read_json, write_json, sha256, now
from ..machine_learning.contract import CONTRACT, TARGET, FEATURES, CROPS
from ..machine_learning.dataset import validate_dataset
from ..machine_learning.spatial import split, assert_no_leakage
from ..machine_learning.training import pipeline, predict, metrics, versions


def owner_hash(owner):
    return hashlib.sha256(owner.encode()).hexdigest()


def authorize(farm_id):
    from ..database import SessionLocal
    from ..models import Farm
    with SessionLocal() as db:
        farm = db.get(Farm, farm_id)
        if farm is None:
            raise ValueError("Farm does not exist")
        path = ROOT / "access.json"
        access = read_json(path) if path.exists() else {"enabled": True, "owners": []}
        access["enabled"] = True
        access["owners"] = sorted(set(access["owners"]) | {owner_hash(farm.owner)})
        write_json(path, access)
        path.chmod(0o600)
    print(f"Authorized development workspace owning farm {farm_id}; production access remains disabled.")


def development_access(open_to_all):
    path = ROOT / "access.json"
    data = read_json(path) if path.exists() else {"enabled": True, "owners": []}
    data.update(enabled=True, allDevelopmentUsers=open_to_all)
    write_json(path, data)
    path.chmod(0o600)
    print("Experimental access: " + ("all development users" if open_to_all else "approved workspaces only")
          + "; production remains disabled.")


def reproduce(dataset):
    if (ROOT / "manifest.json").exists():
        raise ValueError("Experimental bundles already exist; no unnecessary refit")
    expected = read_json("docs/ml-recovery/evidence/expanded-evaluation.json")
    bundle = read_json(dataset)
    frame = split(validate_dataset(bundle), seed=42, buffer_km=150)
    assert_no_leakage(frame, 150)
    actual_splits = sorted((r.cell_id, r.crop, r.split) for r in frame.itertuples())
    old_splits = sorted((r["cell_id"], r["crop"], r["split"]) for r in expected["splits"])
    if actual_splits != old_splits:
        raise ValueError("Original 600-cell experiment partition identities changed")
    records = {}
    # Only five frozen selected candidates; NO CV search or holdout prediction.
    for crop in sorted(CROPS):
        old = expected["crops"][crop]
        selected = old["selected"]
        leaf = {"forest_leaf_3": 3, "forest_leaf_8": 8}[selected]
        tr = frame[(frame.crop == crop) & (frame.split == "train")]
        va = frame[(frame.crop == crop) & (frame.split == "validation")]
        model = pipeline(RandomForestRegressor(n_estimators=150, min_samples_leaf=leaf,
                            n_jobs=2, random_state=42)).fit(tr[FEATURES], tr.target)
        validation = metrics(va.target, predict(model, va))
        prior = old["candidates"][selected]["validation"]["candidate"]["aggregate"]
        if any(not np.isclose(validation[k], prior[k], rtol=0, atol=1e-6) for k in ["mae", "rmse", "r2"]):
            raise ValueError("Restored model does not reproduce original development metrics: " + crop)
        path = ROOT / "models" / f"{crop}-experimental.joblib"
        path.parent.mkdir(parents=True, exist_ok=True)
        obj = {"pipeline": model, "crop": crop, "contract": CONTRACT, "target": TARGET,
               "featureOrder": FEATURES, "datasetHash": bundle["dataset_hash"],
               "productionAccepted": False, "coverage": old["coverage"],
               "declaredRegions": old["declared_regions"]}
        joblib.dump(obj, path)
        path.chmod(0o600)
        records[crop] = {"sha256": sha256(path), "public": {
            "selected": selected, "validationMae": validation["mae"], "validationR2": validation["r2"],
            "meanBaselineMae": old["candidates"][selected]["validation"]["mean"]["aggregate"]["mae"],
            "medianBaselineMae": old["candidates"][selected]["validation"]["median"]["aggregate"]["mae"],
            "validationStatus": "rejected_before_test", "rejectionReasons": old["reasons"],
            "geographicLimitations": "No accepted geographic domain; support screening retained only four development cells.",
            "trainedCells": len(tr), "validationCells": len(va)}}
        print(f"Saved experimental {crop}; reproduced validation MAE={validation['mae']:.6f}", flush=True)
    write_json(ROOT / "manifest.json", {
        "mode": "experimental", "productionAccepted": False, "finalTestEvaluated": False,
        "generatedAt": now(), "modelVersion": "experimental-" + bundle["dataset_hash"][:12],
        "datasetHash": bundle["dataset_hash"], "originalDatasetHash": expected["dataset_hash"],
        "sourceEvaluationSha256": sha256("docs/ml-recovery/evidence/expanded-evaluation.json"),
        "contract": CONTRACT, "target": TARGET, "versions": versions(), "models": records})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["authorize", "reproduce", "open-development", "restrict-development"])
    parser.add_argument("--farm-id", type=int)
    parser.add_argument("--dataset", default="generated-artifacts/ml-recovery/experimental-restored/dataset.json")
    args = parser.parse_args()
    if args.command in {"open-development", "restrict-development"}:
        development_access(args.command == "open-development")
    elif args.command == "authorize":
        if not args.farm_id:
            parser.error("--farm-id is required")
        authorize(args.farm_id)
    else:
        reproduce(args.dataset)
