"""File-only reproducible CLI; no database imports, routes or live activation."""
import argparse
import json
from pathlib import Path

from .common import read_json, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    labels = sub.add_parser("labels")
    labels.add_argument("--root", required=True)
    manual = sub.add_parser("import-labels")
    manual.add_argument("--root", required=True)
    audit = sub.add_parser("audit")
    audit.add_argument("--run-root", required=True)
    audit.add_argument("--out", required=True)
    evidence = sub.add_parser("evidence")
    evidence.add_argument("--run-root", required=True)
    evidence.add_argument("--out", required=True)
    evidence.add_argument("--prepared-name", default="prepared")
    evidence.add_argument("--training-name", default="training")
    samples = sub.add_parser("sample")
    samples.add_argument("--root", required=True)
    samples.add_argument("--out", required=True)
    samples.add_argument("--cells", type=int, default=240)
    samples.add_argument("--seed", type=int, default=42)
    supplement_parser = sub.add_parser("supplement")
    supplement_parser.add_argument("--samples", required=True)
    supplement_parser.add_argument("--out", required=True)
    preparation = sub.add_parser("prepare")
    preparation.add_argument("--samples", required=True)
    preparation.add_argument("--cache", required=True)
    preparation.add_argument("--out", required=True)
    training = sub.add_parser("train")
    training.add_argument("--dataset", required=True)
    training.add_argument("--out", required=True)
    training.add_argument("--config")
    prediction = sub.add_parser("predict")
    prediction.add_argument("--request", required=True)
    prediction.add_argument("--model-dir")
    args = parser.parse_args()
    try:
        if args.command in {"labels", "import-labels"}:
            from .labels import acquire_labels, import_labels
            result = (acquire_labels if args.command == "labels" else import_labels)(args.root)
        elif args.command == "audit":
            from .audit import capture
            result = capture(args.run_root, args.out)
        elif args.command == "evidence":
            from .evidence import finalize
            result = finalize(args.run_root, args.out, args.prepared_name, args.training_name)
        elif args.command == "sample":
            from .labels import import_labels, sample_labels
            if not 1 <= args.cells <= 10000:
                raise ValueError("Request 1–10000 cells per explicitly budgeted batch")
            result = sample_labels(import_labels(args.root), args.cells, args.seed)
            write_json(args.out, result)
            result = {"sample_file": args.out, "label_rows": len(result["records"])}
        elif args.command == "supplement":
            from .supplement import supplement
            result = supplement(args.samples, args.out)
        elif args.command == "prepare":
            from .dataset import prepare
            result = prepare(args.samples, args.cache, args.out)
        elif args.command == "train":
            from .training import train, DEFAULT_CONFIG
            result = train(args.dataset, args.out, args.config or DEFAULT_CONFIG)
        else:
            from .contract import PredictionInput
            from .inference import SuitabilityPredictor
            result = SuitabilityPredictor(args.model_dir).predict(PredictionInput(**read_json(args.request)))
        print(json.dumps(result, indent=2, allow_nan=False))
        return 0 if result.get("status") not in {"insufficient_evidence", "rejected", "rejected_on_validation", "unavailable"} else 2
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "failed", "reason": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
