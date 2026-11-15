"""Summarize a completed real-data run without inventing model results."""
from dataclasses import asdict
from pathlib import Path

from .common import read_json, write_json, sha256
from .contract import FEATURES, PredictionInput
from .inference import SuitabilityPredictor
from .training import train


def evaluation_markdown(result):
    def number(value):
        return "undefined" if value is None else f"{value:.3f}"

    lines = [
        "# Recorded real-data evaluation", "",
        f"Outcome: **{result['status']}**.", "",
        "These metrics, when present, approximate modeled GAEZ index values "
        "(0–10,000); they are not observed crop success or yield.", "",
        "## Geographic sample counts", "",
        "| Partition | Independent source cells |",
        "|---|---:|",
    ]
    for name, count in result.get("split_cells", {}).items():
        lines.append(f"| {name} | {count} |")
    if result.get("validation"):
        lines += ["", "## Training-only CV and validation", "",
                  "| Candidate | Mean fold MAE | Validation MAE | Validation RMSE | Validation R² |",
                  "|---|---:|---:|---:|---:|"]
        for name, item in result["validation"].items():
            score = item["validation"]["aggregate"]
            mean_cv = sum(fold["mae"] for fold in item["spatial_cv"])/len(item["spatial_cv"])
            lines.append(f"| {name} | {number(mean_cv)} | {number(score['mae'])} | "
                         f"{number(score['rmse'])} | {number(score['r2'])} |")
        lines += ["", "Fold MAE above is an unweighted mean of the three buffered training-only "
                  "fold errors. Validation, not final-test performance, selected the candidate.",
                  "", f"Selected candidate: **{result['selected']}**."]
        baseline = result["validation_dummy"]["aggregate"]
        lines += ["", f"Dummy mean baseline validation: MAE **{number(baseline['mae'])}**, "
                  f"RMSE **{number(baseline['rmse'])}**, R² **{number(baseline['r2'])}**."]
        for dimension in ("crop", "region"):
            lines += ["", f"### Selected candidate validation by {dimension}", "",
                      "| Group | Source cells | Rows | MAE | RMSE | R² |",
                      "|---|---:|---:|---:|---:|---:|"]
            for name, item in result["validation"][result["selected"]]["validation"]["per_"+dimension].items():
                lines.append(f"| {name} | {item['cells']} | {item['count']} | "
                             f"{number(item['mae'])} | {number(item['rmse'])} | "
                             f"{number(item['r2'])} |")
    else:
        lines += ["", "No baseline or candidate was fitted: readiness failed."]
    if result.get("test"):
        lines += ["", "## Once-only final geographic holdout", "",
                  "| Estimator | Rows | MAE | RMSE | R² |",
                  "|---|---:|---:|---:|---:|"]
        for name in ("dummy", "crop_mean", "candidate"):
            item = result["test"][name]["aggregate"]
            lines.append(f"| {name} | {item['count']} | {number(item['mae'])} | "
                         f"{number(item['rmse'])} | {number(item['r2'])} |")
        for dimension in ("crop", "region"):
            lines += ["", f"### Selected candidate by {dimension}", "",
                      "| Group | Source cells | Rows | MAE | RMSE | R² |",
                      "|---|---:|---:|---:|---:|---:|"]
            for name, item in result["test"]["candidate"]["per_"+dimension].items():
                lines.append(f"| {name} | {item['cells']} | {item['count']} | "
                             f"{number(item['mae'])} | {number(item['rmse'])} | "
                             f"{number(item['r2'])} |")
        lines += ["", "Region identifiers are geographic diagnostic bins, not verified climate "
                  "zones. Small per-region samples are weaknesses and block promotion."]
    else:
        lines += ["", "The final holdout was not evaluated."]
    lines += ["", "## Readiness / rejection reasons", ""]
    lines += [f"- `{reason}`" for reason in result["reasons"]] or ["- None."]
    lines += ["", f"Deployable model saved: **{result['model_saved']}**. "
              "A rejected candidate is not available for live predictions.", ""]
    return "\n".join(lines)


def finalize(run_root, destination, prepared_name="prepared", training_name="training"):
    root, destination = Path(run_root), Path(destination)
    quality = read_json(root / prepared_name / "quality.json")
    dataset = read_json(root / prepared_name / "dataset.json")
    evaluation = root / training_name / "evaluation.json"
    readiness = root / training_name / "readiness.json"
    # Never repeat a final test simply to regenerate a report.
    if evaluation.exists():
        result = read_json(evaluation)
    elif readiness.exists():
        result = read_json(readiness)
    else:
        result = train(root / prepared_name / "dataset.json", root / training_name)
    if result["dataset_hash"] != dataset["dataset_hash"]:
        raise ValueError("Training evidence belongs to a different dataset")
    write_json(destination / "quality.json", quality)
    write_json(destination / "training-evidence.json", result)
    write_json(destination / "feature-contract.json", result["contract"])
    write_json(destination / "training-config.json", result["config"])
    model_trained = result["status"] in {"accepted", "rejected", "rejected_on_validation"}
    summary = {
        "phase4_complete": result["status"] == "accepted",
        "outcome": result["status"], "readiness_or_rejection_reasons": result["reasons"],
        "dataset_hash": dataset["dataset_hash"],
        "sampled_cells": dataset["sampling"]["requested_cells"],
        "aligned_cells": quality["effective_label_cells"],
        "aligned_rows": quality["final_examples"], "excluded_rows": quality["excluded_rows"],
        "split_cells": result.get("split_cells", {}),
        "genuine_baseline_and_candidates_trained": model_trained,
        "final_holdout_evaluated": "test" in result,
        "deployable_model_saved": result["model_saved"],
        "activated": False, "live_routes_added": False, "production_writes": False,
        "supported_prediction_crops": result["supported_crops"],
        "source_layer_crops": sorted({r["crop"] for r in dataset["source_manifest"]["rasters"]}),
        "environment_cache": {
            "complete_power_responses": len([p for p in (root/"environment").glob("power-*.json")
                                            if not p.name.endswith(".source.json")]),
            "native_soil_vrts": len(list((root/"environment").glob("*_0-5cm_mean.vrt"))),
            "native_soil_tiles": len(list((root/"environment").glob("tile-*.tif"))),
        },
        "local_dataset_path": str(root / prepared_name / "dataset.json"),
        "reproducibility_notice": "Large source/cache files remain in ignored local research storage; use recorded URLs/hashes to reacquire",
    }
    if dataset["records"]:
        row = dataset["records"][0]
        request = PredictionInput(latitude=row["latitude"], longitude=row["longitude"],
                                  features={k: row[k] for k in FEATURES})
        write_json(destination / "example-request.json", asdict(request))
        response = SuitabilityPredictor(root/training_name).predict(request)
        write_json(destination / "example-response.json", response)
        summary["example_response_status"] = response["status"]
        summary["example_is_real_model_prediction"] = response["available"]
    checks = {}
    for name in ("all-tests.log", "ml-tests-final.log", "typecheck.log"):
        path = root / name
        if path.exists():
            lines = path.read_text().splitlines()
            checks[name] = {"sha256": sha256(path), "final_lines": lines[-6:]}
    summary["executed_checks"] = checks
    write_json(destination / "run-summary.json", summary)
    (destination / "evaluation.md").write_text(evaluation_markdown(result))
    return summary
