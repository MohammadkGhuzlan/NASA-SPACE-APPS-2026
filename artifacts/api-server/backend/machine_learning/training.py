"""Supervised regression with predeclared gates and one-use geographic holdout."""
import importlib.metadata
from pathlib import Path

import joblib
import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.base import clone
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold
from sklearn.neighbors import NearestNeighbors
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .common import digest, now, read_json, sha256, write_json
from .contract import CONTRACT, CROPS, FEATURES, NUMERIC, CATEGORICAL, TARGET, LIMITATIONS
from .dataset import validate_dataset
from .spatial import split, assert_no_leakage, buffered_cv

DEFAULT_CONFIG = Path(__file__).with_name("config.json")
LIBRARIES = ["scikit-learn", "numpy", "pandas", "joblib", "scipy", "rasterio", "pyproj"]


def versions():
    return {name: importlib.metadata.version(name) for name in LIBRARIES}


def pipeline(estimator):
    return Pipeline([
        ("features", ColumnTransformer([
            ("numeric", StandardScaler(), NUMERIC),
            ("categorical", OneHotEncoder(handle_unknown="error", sparse_output=False), CATEGORICAL),
        ], remainder="drop")),
        ("model", estimator),
    ])


def predict(model, frame):
    return np.clip(model.predict(frame[FEATURES]), 0, 10000)


def metrics(actual, predicted):
    actual, predicted = np.asarray(actual), np.asarray(predicted)
    return {"count": len(actual), "mae": float(mean_absolute_error(actual, predicted)),
            "rmse": float(np.sqrt(mean_squared_error(actual, predicted))),
            "r2": float(r2_score(actual, predicted)) if len(actual) > 1 and np.ptp(actual) > 0 else None}


def breakdown(frame, predictions):
    result = {"aggregate": metrics(frame.target, predictions)}
    for column in ("crop", "region"):
        result["per_" + column] = {}
        for name in sorted(frame[column].unique()):
            selected = (frame[column] == name).to_numpy()
            result["per_" + column][name] = {
                **metrics(frame.loc[selected, "target"], np.asarray(predictions)[selected]),
                "cells": int(frame.loc[selected, "cell_id"].nunique()),
            }
    return result


def readiness(frame, config):
    reasons = []
    if not len(frame):
        return ["no_aligned_examples"]
    if frame.cell_id.nunique() < config["minimum_cells"]:
        reasons.append("insufficient_independent_source_cells")
    for name in ("train", "validation", "test"):
        group = frame[frame.split == name]
        if group.cell_id.nunique() < config[f"minimum_{name}_cells"]:
            reasons.append(f"insufficient_{name}_cells")
        if group.block.nunique() < config["minimum_blocks_per_partition"]:
            reasons.append(f"insufficient_{name}_geographic_blocks")
        if set(group.crop) != set(CROPS):
            reasons.append(f"missing_{name}_crops")
        # Only training/validation distributions may gate on target span.
        if name != "test":
            for crop, g in group.groupby("crop"):
                if np.ptp(g.target) < config["minimum_label_span"]:
                    reasons.append(f"insufficient_{name}_label_span:{crop}")
    return reasons


def acceptance(report, config):
    failures = []
    final, baseline = report["candidate"], report["dummy"]
    if set(final["per_crop"]) != set(CROPS) or not final["per_region"]:
        failures.append("incomplete_crop_or_region_evidence")
    for name in ("candidate", "dummy", "crop_mean"):
        for item in [report[name]["aggregate"],
                     *report[name].get("per_crop", {}).values(),
                     *report[name].get("per_region", {}).values()]:
            if not all(np.isfinite(item[k]) for k in ("mae", "rmse") if k in item):
                failures.append("nonfinite_evaluation_metrics")
    score = final["aggregate"]
    if score["mae"] > config["maximum_mae"]:
        failures.append("aggregate_mae")
    if score["r2"] is None or not np.isfinite(score["r2"]) or score["r2"] < config["minimum_r2"]:
        failures.append("aggregate_r2")
    if score["mae"] > baseline["aggregate"]["mae"] * (1-config["minimum_relative_mae_gain"]):
        failures.append("no_meaningful_dummy_improvement")
    if score["mae"] > report["crop_mean"]["aggregate"]["mae"] * (1-config["minimum_relative_mae_gain"]):
        failures.append("no_meaningful_crop_mean_improvement")
    for crop, item in final["per_crop"].items():
        if item["cells"] < config["minimum_test_cells_per_crop"]:
            failures.append(f"insufficient_test_support:{crop}")
        if item["mae"] > config["maximum_crop_mae"]:
            failures.append(f"crop_error:{crop}")
        if item["mae"] > report["crop_mean"]["per_crop"][crop]["mae"]:
            failures.append(f"crop_worse_than_baseline:{crop}")
    for region, item in final["per_region"].items():
        if item["cells"] < config["minimum_test_cells_per_region"]:
            failures.append(f"insufficient_test_region_support:{region}")
        elif item["mae"] > config["maximum_region_mae"]:
            failures.append(f"region_error:{region}")
    return failures


def train(dataset_path, output, config_path=DEFAULT_CONFIG):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    if (output / "accepted.joblib").exists() or (output / "evaluation.json").exists():
        raise ValueError("Existing evidence/artifact will not be overwritten; inspect it first")
    bundle = read_json(dataset_path)
    config = read_json(config_path)
    frame = validate_dataset(bundle)
    # Carry exact environmental object identities with evaluation/model evidence,
    # not only a label-raster manifest and an opaque dataset checksum.
    environmental_objects = {}
    climate_versions, soil_versions = {}, {}
    for row in bundle["records"]:
        power = row["climate_evidence"]
        environmental_objects[power["sha256"]] = {
            k: power[k] for k in ("sha256", "url", "retrieved_at", "header")}
        climate_versions[digest(power["header"]["api"])] = {
            "api": power["header"]["api"], "sources": power["header"].get("sources", [])}
        for prop, source in row["soil_evidence"].items():
            soil_versions[prop] = {"vrt_sha256": source["vrt_sha256"],
                                   "product": source["product"], "depth_cm": source["depth_cm"]}
            for tile in source["tiles"]:
                environmental_objects[tile["sha256"]] = {
                    k: tile[k] for k in ("sha256", "url", "retrieved_at")}
    evidence = {
        "status": "insufficient_evidence", "trained_at": now(),
        "contract": CONTRACT, "target": TARGET, "limitations": LIMITATIONS,
        "config": config, "config_hash": digest(config), "dataset_hash": bundle["dataset_hash"],
        "source_manifest": bundle["source_manifest"], "versions": versions(),
        "supported_crops": [], "supported_scenarios": [], "model_saved": False,
        "dataset_manifest": {
            "dataset_hash": bundle["dataset_hash"], "dataset_path": str(dataset_path),
            "record_count": len(frame), "sample_file_sha256": bundle["samples_sha256"],
            "sampling": bundle["sampling"], "environmental_sources": list(environmental_objects.values()),
        },
        "data_source_versions": {
            "labels": {"publisher": "FAO/IIASA", "version": "GAEZ v5",
                       "mapset": TARGET["mapset"]},
            "climate": list(climate_versions.values()), "soil": soil_versions,
        },
    }
    if not len(frame):
        evidence["reasons"] = ["no_aligned_examples"]
        write_json(output / "readiness.json", evidence)
        return evidence
    frame = split(frame, config["seed"], config["buffer_km"])
    assert_no_leakage(frame, config["buffer_km"])
    evidence["split_counts"] = {str(k): int(v) for k, v in frame.groupby("split").size().items()}
    evidence["split_cells"] = {str(k): int(v) for k, v in frame.groupby("split").cell_id.nunique().items()}
    evidence["splits"] = frame[["cell_id", "crop", "block", "region", "split"]].to_dict("records")
    reasons = readiness(frame, config)
    evidence["reasons"] = reasons
    write_json(output / "readiness.json", evidence)
    if reasons:
        return evidence
    tr = frame[frame.split == "train"].reset_index(drop=True)
    va = frame[frame.split == "validation"].reset_index(drop=True)
    te = frame[frame.split == "test"].reset_index(drop=True)
    dummy = pipeline(DummyRegressor(strategy="mean")).fit(tr[FEATURES], tr.target)
    crop_means = tr.groupby("crop").target.mean().to_dict()
    candidates = [
        (f"ridge_{alpha}", Ridge(alpha=alpha)) for alpha in config["ridge_alpha"]
    ] + [
        (f"forest_leaf_{leaf}", RandomForestRegressor(
            n_estimators=config["forest_trees"], min_samples_leaf=leaf,
            random_state=config["seed"], n_jobs=2))
        for leaf in config["forest_min_samples_leaf"]
    ]
    validation = {}
    fitted = {}
    folds = list(buffered_cv(tr, GroupKFold(n_splits=3).split(tr, groups=tr.block),
                             config["buffer_km"]))
    evidence["training_cv_folds"] = [
        {"train_cells": sorted(tr.iloc[a].cell_id.unique().tolist()),
         "validation_cells": sorted(tr.iloc[b].cell_id.unique().tolist())}
        for a, b in folds]
    for name, estimator in candidates:
        fold_scores = []
        for train_idx, validation_idx in folds:
            model = pipeline(clone(estimator))
            model.fit(tr.iloc[train_idx][FEATURES], tr.iloc[train_idx].target)
            fold_scores.append(metrics(tr.iloc[validation_idx].target,
                                       predict(model, tr.iloc[validation_idx])))
        model = pipeline(estimator).fit(tr[FEATURES], tr.target)
        fitted[name] = model
        validation[name] = {"spatial_cv": fold_scores,
                            "validation": breakdown(va, predict(model, va))}
    selected = min(validation, key=lambda n: validation[n]["validation"]["aggregate"]["mae"])
    model = fitted[selected]
    evidence.update(selected=selected, validation=validation,
                    validation_dummy=breakdown(va, predict(dummy, va)))
    # Every known validation failure must stop final testing, not just MAE.
    validation_report = {
        "candidate": validation[selected]["validation"],
        "dummy": evidence["validation_dummy"],
        "crop_mean": breakdown(va, va.crop.map(crop_means).to_numpy()),
    }
    evidence["validation_crop_mean"] = validation_report["crop_mean"]
    validation_failures = acceptance(validation_report, config)
    if validation_failures:
        evidence.update(status="rejected_on_validation",
                        reasons=["validation_" + reason for reason in validation_failures])
        write_json(output / "evaluation.json", evidence)
        return evidence
    # Reserve the final holdout once per immutable dataset, not once per output directory.
    ledger = Path(dataset_path).parent / ".holdout" / (bundle["dataset_hash"] + ".json")
    if ledger.exists():
        raise FileExistsError("Existing dataset holdout reservation; refusing reuse")
    from .holdout import reserve
    evidence["geographic_holdout_reservation"] = reserve(
        te.block.unique(), seed=config["seed"],
        run_identity={"dataset_hash": bundle["dataset_hash"], "output": str(output)})
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("x") as stream:
        import json
        json.dump({"reserved_at": now(), "config_hash": digest(config), "selected": selected,
                   "output": str(output)}, stream)
    # No refit on validation/test. All fitted preprocessing remains training-only.
    final = {
        "candidate": breakdown(te, predict(model, te)),
        "dummy": breakdown(te, predict(dummy, te)),
        "crop_mean": breakdown(te, te.crop.map(crop_means).to_numpy()),
    }
    failures = acceptance(final, config)
    evidence.update(test=final, reasons=failures, status="rejected" if failures else "accepted")
    if not failures:
        scale = StandardScaler().fit(tr[NUMERIC])
        neighbors = NearestNeighbors(n_neighbors=1).fit(scale.transform(tr[NUMERIC]))
        distances = neighbors.kneighbors(scale.transform(va[NUMERIC]))[0][:, 0]
        support = {
            "ranges": {k: [float(tr[k].min()), float(tr[k].max())] for k in NUMERIC},
            "heldout_blocks": sorted(te.block.unique().tolist()),
            "training_environments": tr.drop_duplicates("cell_id")[NUMERIC].to_dict("records"),
            "distance_threshold": float(np.quantile(distances, config["validation_distance_quantile"])),
            "scaler_mean": scale.mean_.tolist(), "scaler_scale": scale.scale_.tolist(),
            "definition": "All numeric training ranges AND validation-derived joint-distance limit AND tested geographic block",
        }
        evidence.update(supported_crops=sorted(CROPS), supported_scenarios=["LRLM"],
                        support=support, model_version="gaez-" + bundle["dataset_hash"][:12],
                        contract_hash=digest(CONTRACT), model_saved=True)
        artifact = output / "accepted.joblib"
        joblib.dump({"pipeline": model, "contract": CONTRACT,
                     "dataset_hash": bundle["dataset_hash"]}, artifact)
        evidence["artifact_sha256"] = sha256(artifact)
    write_json(output / "evaluation.json", evidence)
    return evidence
