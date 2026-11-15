"""Reproducible source recovery, legacy diagnosis and budgeted data preparation.

Run with ``python -m backend.machine_learning.recovery --help``.
This tool never activates models or touches the application database.
"""
import argparse
from collections import Counter
from pathlib import Path
import resource
import time

import numpy as np

from .common import digest, read_json, sha256, write_json, now
from .contract import CONTRACT
from .labels import import_labels, sample_labels
from .spatial import block, partition, near
from .supplement import supplement


def reconstruct(root, evidence):
    root, evidence = Path(root), Path(evidence)
    manifest = import_labels(root / "labels")
    original = read_json(evidence / "source-audit.json")["labels"]
    actual = {r["crop"]: r["sha256"] for r in manifest["rasters"]}
    expected = {r["crop"]: r["sha256"] for r in original["rasters"]}
    if actual != expected:
        raise ValueError("original_label_bytes_not_recovered")
    samples = sample_labels(manifest, count=180, seed=42)
    write_json(root / "samples.json", samples)
    supplement(root / "samples.json", root / "supplemented-samples.json")
    samples = read_json(root / "supplemented-samples.json")
    old = read_json(evidence / "training-evidence.json")
    sampled = {(r["cell_id"], r["crop"]) for r in samples["records"]}
    retained = {(r["cell_id"], r["crop"]) for r in old["splits"]}
    exclusions = {r["cell_id"] for r in read_json(evidence / "quality.json")["exclusions"]}
    if (not retained.issubset(sampled) or
            {r["cell_id"] for r in samples["records"]} !=
            {r[0] for r in retained} | exclusions):
        raise ValueError("original_sample_identity_not_reproduced")
    return samples


def diagnose(root, evidence, out):
    """Compute actual label summaries; never refit or evaluate the old holdout."""
    root, evidence = Path(root), Path(evidence)
    samples = reconstruct(root, evidence)
    old = read_json(evidence / "training-evidence.json")
    quality = read_json(evidence / "quality.json")
    kept = {r["cell_id"] for r in old["splits"]}
    splits = {r["cell_id"]: r for r in old["splits"]}
    rows = [r for r in samples["records"] if r["cell_id"] in kept]
    config = old["config"]
    distributions = {}
    # Overall distribution was already disclosed in the original quality report.
    # Do not introduce test-specific label statistics during model development.
    for crop in sorted({r["crop"] for r in rows}):
        values = np.array([r["target"] for r in rows if r["crop"] == crop])
        distributions[crop] = {
            "count": len(values), "zero_count": int((values == 0).sum()),
            "min": int(values.min()), "max": int(values.max()),
            "mean": float(values.mean()),
            "quantiles_0_25_50_75_100": np.quantile(values, [0, .25, .5, .75, 1]).tolist(),
            "target_type": "continuous index; not classes",
        }
    candidates = {}
    dummy = old["validation_dummy"]["aggregate"]["mae"]
    for name, result in old["validation"].items():
        score = result["validation"]["aggregate"]
        failures = []
        if score["mae"] > config["maximum_mae"]:
            failures.append("validation_mae")
        if score["r2"] is None or score["r2"] < config["minimum_r2"]:
            failures.append("validation_r2")
        if score["mae"] > dummy * (1 - config["minimum_relative_mae_gain"]):
            failures.append("validation_dummy_gain")
        candidates[name] = {**score, "screening_failures_visible_from_recorded_metrics": failures,
                            "recorded_cv": result["spatial_cv"]}
    # Recompute the train-only crop-mean diagnostic from the byte-identical
    # source labels; validation is development data, final-test is not read here.
    crop_mean_errors = {}
    for crop in distributions:
        train_values = [r["target"] for r in rows if r["crop"] == crop and splits[r["cell_id"]]["split"] == "train"]
        validation_values = [r["target"] for r in rows if r["crop"] == crop and splits[r["cell_id"]]["split"] == "validation"]
        mean = float(np.mean(train_values))
        median = float(np.median(train_values))
        crop_mean_errors[crop] = {
            "training_mean": mean, "training_median": median,
            "validation_mae": float(np.abs(np.array(validation_values) - mean).mean()),
            "median_validation_mae": float(np.abs(np.array(validation_values) - median).mean())}
    partition_counts = {}
    for name in ("train", "validation", "test"):
        selected = {r["cell_id"]: r for r in old["splits"] if r["split"] == name}
        partition_counts[name] = {"cells": len(selected),
                                  "blocks": len({r["block"] for r in selected.values()}),
                                  "regions": len({r["region"] for r in selected.values()})}
    result = {
        "generated_at": now(), "old_evidence_sha256": sha256(evidence / "training-evidence.json"),
        "protocol_sha256": sha256("docs/ml-recovery/PROTOCOL.md"),
        "source_rasters_byte_identical": True, "original_sample_identities_recovered": True,
        "sampled_cells": 300, "retained_cells": len(kept), "retained_rows": len(rows),
        "excluded_cells": len(quality["exclusions"]), "partitions": partition_counts,
        "exclusion_counts": dict(Counter(x["reason"].split(":")[0] for x in quality["exclusions"])),
        "contract": CONTRACT, "continuous_target_distributions": distributions,
        "candidates": candidates, "dummy_validation": old["validation_dummy"],
        "reconstructed_crop_mean_baseline": crop_mean_errors,
        "additional_median_baseline_diagnostic": {
            "validation_mae": float(np.mean([r["median_validation_mae"] for r in crop_mean_errors.values()])),
            "meaning": "Train-only crop median is MAE-optimal constant; additional diagnostic, not the recorded original rejection gate"},
        "selected_candidate": old["selected"], "recorded_rejection": old["reasons"],
        "final_test_evaluated": False,
        "demonstrated": [
            "Selected validation MAE exceeds the frozen maximum",
            "All four candidates also fail R2 and meaningful dummy improvement screens",
            "176 of 300 sampled cells excluded by native soil coverage",
            "Five crop rows repeat one environmental cell; not five independent environments",
            "Sparse diagnostic regions cannot support the previous regional promotion gate",
            "Original research sources/dataset/estimators absent at recovery start",
        ],
        "hypotheses_not_established_causes": [
            "POWER/MERRA2 versus AgERA5 climate product mismatch limits target approximation",
            "Static shallow soil features omit relevant GAEZ constraints",
            "Soil complete-case attrition introduces geographic selection bias",
            "Zero-heavy all-land targets require more representative sampling",
        ],
        "not_demonstrated": ["unit bug", "crop-code bug", "fabricated GAEZ labels",
                             "period relabeling", "a model that passes independent testing"],
    }
    write_json(out, result)
    return result


def expand(samples, root):
    """Fixed seed-44 pool; no access to targets when deciding cell membership."""
    candidates = sample_labels(samples["source_manifest"], count=1800, seed=44)
    groups = {}
    for row in candidates["records"]:
        groups.setdefault(row["cell_id"], []).append(row)
    old = {r["cell_id"]: r for r in samples["records"]}
    points = [(r["longitude"], r["latitude"]) for r in old.values()]
    additional = []
    for key, group in groups.items():
        row = group[0]
        point = row["longitude"], row["latitude"]
        if key in old or any(near(point, p, 150) for p in points):
            continue
        points.append(point)
        additional.extend(group)
        if len(additional) == 1500:
            break
    if len(additional) != 1500:
        raise ValueError("insufficient_spaced_seed44_candidates")
    result = {**samples, "requested_cells": 600,
              "sampling": samples["sampling"] + "\nRecovery seed-44 pool 1800; 300 target-independent spaced cells.",
              "records": samples["records"] + additional}
    write_json(Path(root) / "expanded-samples.json", result)
    return result


def acquire(root, evidence, *, seconds=2700, max_bytes=1_610_612_736):
    from .budget import ResearchBudget, BudgetExceeded
    from .dataset import prepare
    root = Path(root)
    if (root / "acquisition-result.json").exists():
        raise ValueError("acquisition_result_exists_use_new_run_directory")
    started = time.monotonic()
    budget = ResearchBudget(root, seconds=seconds, max_bytes=max_bytes)
    result = {"started_at": now(), "completed": False, "protocol_sha256": sha256("docs/ml-recovery/PROTOCOL.md")}
    try:
        samples = read_json(root / "supplemented-samples.json")
        first = prepare(root / "supplemented-samples.json", root / "environment", root / "restored", budget=budget)
        result["restored"] = first
        expand(samples, root)
        result["expanded"] = prepare(root / "expanded-samples.json", root / "environment", root / "expanded", budget=budget)
        result["completed"] = True
    except (BudgetExceeded, ValueError, OSError) as exc:
        result["stop_reason"] = str(exc)
    finally:
        usage = resource.getrusage(resource.RUSAGE_SELF)
        result.update(ended_at=now(), elapsed_seconds=time.monotonic()-started,
                      cpu_seconds=usage.ru_utime+usage.ru_stime, peak_rss_kib=usage.ru_maxrss,
                      cache_bytes=sum(p.stat().st_size for p in root.rglob("*") if p.is_file()))
        write_json(root / "acquisition-result.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["diagnose", "acquire"])
    parser.add_argument("--root", default="generated-artifacts/ml-recovery")
    parser.add_argument("--evidence", default="docs/phase4/evidence")
    parser.add_argument("--out", default="docs/ml-recovery/evidence/diagnosis.json")
    args = parser.parse_args()
    result = (diagnose(args.root, args.evidence, args.out) if args.command == "diagnose"
              else acquire(args.root, args.evidence))
    print({"completed": result.get("completed"), "out": args.out if args.command == "diagnose" else args.root})


if __name__ == "__main__":
    main()
