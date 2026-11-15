"""Per-crop recovery experiment. No web activation and no test peeking.

Selection uses training/validation only. Inadequate geographic support is an
explicit rejection, not a reason to relax the accuracy gates.
"""
import argparse
from pathlib import Path
import resource
import time

import joblib
import numpy as np
from sklearn.base import clone
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import StandardScaler

from .common import digest, read_json, sha256, write_json, now
from .contract import CONTRACT, CROPS, FEATURES, NUMERIC, TARGET
from .dataset import validate_dataset
from .spatial import split, assert_no_leakage, buffered_cv
from .training import DEFAULT_CONFIG, breakdown, metrics, pipeline, predict, versions


def gates(report, *, minimum_cells=20, minimum_regions=1):
    """Frozen per-crop/domain screens; all failures, finite metrics, no confidence."""
    reasons = []
    score = report["candidate"]["aggregate"]
    if not all(np.isfinite(score[k]) for k in ("mae", "rmse")):
        reasons.append("nonfinite_metrics")
    if score["count"] < minimum_cells:
        reasons.append("insufficient_independent_cells")
    if report["candidate"].get("geographic_blocks", 0) < 6:
        reasons.append("insufficient_geographic_blocks")
    if score["mae"] > 1500:
        reasons.append("mae")
    if score["r2"] is None or not np.isfinite(score["r2"]) or score["r2"] < .2:
        reasons.append("r2")
    for name in ("mean", "median"):
        baseline = report[name]["aggregate"]["mae"]
        if not np.isfinite(baseline) or score["mae"] > .9 * baseline:
            reasons.append("no_meaningful_" + name + "_improvement")
    regions = report["candidate"]["per_region"]
    if len(regions) < minimum_regions:
        reasons.append("no_supported_region")
    for name, item in regions.items():
        if item["cells"] < 5:
            reasons.append("insufficient_region_cells:" + name)
        if not np.isfinite(item["mae"]) or item["mae"] > 2000:
            reasons.append("region_error:" + name)
    return reasons


def domain_regions(train, validation):
    """Counts only, no test targets or geographic error cherry-picking."""
    a = train.groupby("region").cell_id.nunique()
    b = validation.groupby("region").cell_id.nunique()
    return sorted(name for name in a.index if a[name] >= 10 and b.get(name, 0) >= 5)


def reports(frame, values, mean, median):
    return {"candidate": {**breakdown(frame, values),
                          "independent_cells": int(frame.cell_id.nunique()),
                          "geographic_blocks": int(frame.block.nunique())},
            "mean": breakdown(frame, np.full(len(frame), mean)),
            "median": breakdown(frame, np.full(len(frame), median))}


def fit(dataset_path, output):
    """Save immutable real-data metrics; estimator saved only after acceptance."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    result_path = output / "recovery-evaluation.json"
    if result_path.exists():
        raise ValueError("Recovery evidence is immutable; use a new output directory")
    started = time.monotonic()
    bundle = read_json(dataset_path)
    frame = validate_dataset(bundle)  # full source/hash/feature replay, no trust-CSV mode
    config = read_json(DEFAULT_CONFIG)
    frame = split(frame, seed=42, buffer_km=150)
    assert_no_leakage(frame, 150)
    evidence = {"started_at": now(), "protocol_sha256": sha256("docs/ml-recovery/PROTOCOL.md"),
                "dataset_hash": bundle["dataset_hash"], "contract": CONTRACT, "target": TARGET,
                "dataset_path": str(dataset_path), "source_manifest": bundle["source_manifest"],
                "versions": versions(), "crops": {}, "accepted_crops": [],
                "final_test_evaluated": False, "model_saved": False,
                "splits": frame[["cell_id", "crop", "block", "region", "split"]].to_dict("records"),
                "partition_cells": frame.groupby("split").cell_id.nunique().to_dict(),
                "partition_blocks": frame.groupby("split").block.nunique().to_dict()}
    estimators = [
        ("ridge_1", Ridge(alpha=1)), ("ridge_10", Ridge(alpha=10)),
        ("forest_leaf_3", RandomForestRegressor(n_estimators=150, min_samples_leaf=3, n_jobs=2, random_state=42)),
        ("forest_leaf_8", RandomForestRegressor(n_estimators=150, min_samples_leaf=8, n_jobs=2, random_state=42)),
        ("histogram", HistGradientBoostingRegressor(max_iter=100, max_leaf_nodes=15, l2_regularization=1, random_state=42)),
    ]
    finalists = {}
    for crop in sorted(CROPS):
        group = frame[frame.crop == crop].reset_index(drop=True)
        tr = group[group.split == "train"].reset_index(drop=True)
        va = group[group.split == "validation"].reset_index(drop=True)
        te = group[group.split == "test"].reset_index(drop=True)
        crop_evidence = {"status": "insufficient_evidence", "reasons": [], "candidates": {},
                         "partition_cells": group.groupby("split").cell_id.nunique().to_dict(),
                         "partition_blocks": group.groupby("split").block.nunique().to_dict()}
        evidence["crops"][crop] = crop_evidence
        for name, part, floor in [("train", tr, 60), ("validation", va, 20), ("test", te, 20)]:
            if len(part) < floor or part.block.nunique() < 6:
                crop_evidence["reasons"].append("insufficient_" + name + "_cells_or_blocks")
            if name != "test" and (not len(part) or np.ptp(part.target) < 3000):
                crop_evidence["reasons"].append("insufficient_" + name + "_target_span")
        if crop_evidence["reasons"]:
            continue
        mean, median = float(tr.target.mean()), float(tr.target.median())
        crop_evidence["training_baselines"] = {"mean": mean, "median": median}
        spatial = list(buffered_cv(tr, GroupKFold(3).split(tr, groups=tr.block), 150))
        # Non-spatial diagnostic explicitly grouped by shared environmental cell.
        diagnostic = list(GroupKFold(3).split(tr, groups=tr.cell_id))
        crop_evidence["folds"] = {
            method: [{"train_cell_ids": tr.iloc[a].cell_id.tolist(),
                      "validation_cell_ids": tr.iloc[b].cell_id.tolist()} for a, b in folds]
            for method, folds in [("buffered_spatial", spatial), ("nonspatial_cell_grouped", diagnostic)]}
        fitted = {}
        for name, estimator in estimators:
            model_start = time.monotonic()
            cv = {}
            for method, folds in [("buffered_spatial", spatial), ("nonspatial_cell_grouped", diagnostic)]:
                scores = []
                for a, b in folds:
                    model = pipeline(clone(estimator)).fit(tr.iloc[a][FEATURES], tr.iloc[a].target)
                    score = metrics(tr.iloc[b].target, predict(model, tr.iloc[b]))
                    fold_mean, fold_median = float(tr.iloc[a].target.mean()), float(tr.iloc[a].target.median())
                    scores.append({"candidate": score,
                                   "mean_baseline": metrics(tr.iloc[b].target, np.full(len(b), fold_mean)),
                                   "median_baseline": metrics(tr.iloc[b].target, np.full(len(b), fold_median)),
                                   "train_cells": len(a), "validation_cells": len(b)})
                cv[method] = scores
            model = pipeline(clone(estimator)).fit(tr[FEATURES], tr.target)
            fitted[name] = model
            crop_evidence["candidates"][name] = {
                "estimator_parameters": estimator.get_params(),
                "cv": cv, "validation": reports(va, predict(model, va), mean, median),
                "elapsed_seconds": time.monotonic()-model_start}
        selected = min(fitted, key=lambda n: crop_evidence["candidates"][n]["validation"]["candidate"]["aggregate"]["mae"])
        crop_evidence["selected"] = selected
        crop_evidence["global_validation_failures"] = gates(crop_evidence["candidates"][selected]["validation"])
        eligible = domain_regions(tr, va)
        crop_evidence["declared_regions"] = eligible
        if not eligible:
            crop_evidence.update(status="rejected_before_test", reasons=["no_adequately_supported_domain"])
            continue
        # Domain and support threshold frozen using training/validation only.
        domain_train = tr[tr.region.isin(eligible)]
        domain_va = va[va.region.isin(eligible)]
        scale = StandardScaler()
        scale.fit(domain_train[NUMERIC])
        train_points = scale.transform(domain_train[NUMERIC])
        va_points = scale.transform(domain_va[NUMERIC])
        distances = np.linalg.norm(va_points[:, None, :] - train_points[None, :, :], axis=2).min(axis=1)
        threshold = float(np.quantile(distances, .95))
        ranges = {k: [float(domain_train[k].min()), float(domain_train[k].max())] for k in NUMERIC}

        def retained(part):
            if not len(part):
                return part
            points = scale.transform(part[NUMERIC])
            distance = np.linalg.norm(points[:, None, :] - train_points[None, :, :], axis=2).min(axis=1)
            keep = part.region.isin(eligible).to_numpy() & (distance <= threshold)
            for key, (low, high) in ranges.items():
                keep &= part[key].between(low, high).to_numpy()
            return part.loc[keep]

        kept_va = retained(domain_va)
        crop_evidence["coverage"] = {
            "ranges": ranges, "distance_threshold": threshold, "scaler_mean": scale.mean_.tolist(),
            "scaler_scale": scale.scale_.tolist(), "training_environments": domain_train[NUMERIC].to_dict("records"),
            "validation_total": len(va), "validation_retained": len(kept_va),
            "definition": "declared regions AND training ranges AND validation-calibrated joint distance"}
        if not len(kept_va):
            crop_evidence.update(status="rejected_before_test", reasons=["no_validation_coverage"])
            continue
        model = fitted[selected]
        evaluation = reports(kept_va, predict(model, kept_va), mean, median)
        crop_evidence["supported_validation"] = evaluation
        failures = gates(evaluation, minimum_regions=len(eligible))
        if failures:
            crop_evidence.update(status="rejected_before_test", reasons=failures)
            continue
        finalists[crop] = (model, te, mean, median, eligible)
    if finalists:
        # Save selection/scope BEFORE looking at any final-test outcomes.
        write_json(output / "frozen-selection.json", evidence)
        from .holdout import reserve
        reservation = reserve(
            frame[frame.split == "test"].block.unique(), seed=42,
            run_identity={"dataset_hash": bundle["dataset_hash"], "protocol_sha256": evidence["protocol_sha256"]})
        evidence["holdout_reservation"] = reservation
        evidence["final_test_evaluated"] = True
        for crop, (model, te, mean, median, eligible) in finalists.items():
            item = evidence["crops"][crop]
            # Rebuild coverage for this crop: never capture another crop's
            # loop-local closure when several crops are independently eligible.
            support = item["coverage"]
            def in_scope(row):
                if row.region not in eligible:
                    return False
                point = np.array([getattr(row, k) for k in NUMERIC])
                points = np.array([[r[k] for k in NUMERIC] for r in support["training_environments"]])
                scales = np.array(support["scaler_scale"])
                distance = np.linalg.norm((points-point)/scales, axis=1).min()
                return distance <= support["distance_threshold"] and all(
                    low <= getattr(row, k) <= high for k, (low, high) in support["ranges"].items())
            mask = [in_scope(r) for r in te.itertuples()]
            kept = te.loc[mask]
            item["test_total"], item["test_retained"] = len(te), len(kept)
            failures = ["no_test_coverage"] if not len(kept) else []
            if len(kept):
                item["test"] = reports(kept, predict(model, kept), mean, median)
                failures = gates(item["test"], minimum_regions=len(eligible))
            item.update(status="rejected_on_test" if failures else "accepted", reasons=failures)
            if not failures:
                artifact = output / (crop + "-accepted.joblib")
                joblib.dump({"pipeline": model, "contract": CONTRACT, "crop": crop,
                             "dataset_hash": bundle["dataset_hash"]}, artifact)
                item.update(artifact_sha256=sha256(artifact), artifact_path=str(artifact),
                            model_version="recovery-" + crop + "-" + bundle["dataset_hash"][:12])
                evidence["accepted_crops"].append(crop)
                evidence["model_saved"] = True
    usage = resource.getrusage(resource.RUSAGE_SELF)
    evidence.update(ended_at=now(), elapsed_seconds=time.monotonic()-started,
                    cpu_seconds=usage.ru_utime+usage.ru_stime, peak_rss_kib=usage.ru_maxrss,
                    status="accepted_scope_requires_operator_review" if evidence["accepted_crops"] else "no_accepted_scope")
    write_json(result_path, evidence)
    return evidence


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    result = fit(args.dataset, args.out)
    print({"status": result["status"], "accepted_crops": result["accepted_crops"]})
