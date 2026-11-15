"""Restore only the previously retained 600-cell experiment, not a new sample.

Uses authoritative saved membership/exclusions, replays real source features,
and never fits or predicts on the final holdout. Not imported by HTTP routes.
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import time

from .common import digest, read_json, write_json, sha256, now
from .labels import acquire_labels
from .recovery import reconstruct, expand
from .environment import acquire_power, acquire_soil
from .contract import CONTRACT, PERIOD, TARGET, validate_features
from .budget import ResearchBudget
from .dataset import quality_report

ROOT = Path("generated-artifacts/ml-recovery")
EVIDENCE = Path("docs/ml-recovery/evidence")


def restore():
    started = time.monotonic()
    output = ROOT / "experimental-restored"
    if (output / "dataset.json").exists():
        print("Existing restored dataset retained; no downloads repeated.", flush=True)
        return
    budget = ResearchBudget(ROOT, seconds=2700, max_bytes=1_610_612_736)
    manifest = acquire_labels(ROOT / "labels")
    old = read_json(EVIDENCE / "expanded-evaluation.json")
    if {r["crop"]: r["sha256"] for r in manifest["rasters"]} != {
            r["crop"]: r["sha256"] for r in old["source_manifest"]["rasters"]}:
        raise ValueError("Source label hashes changed; restoration refused")
    samples = expand(reconstruct(ROOT, "docs/phase4/evidence"), ROOT)
    prior_cells = {r["cell_id"] for r in old["splits"]}
    groups = {}
    for row in samples["records"]:
        if row["cell_id"] in prior_cells:
            groups.setdefault(row["cell_id"], []).append(row)
    if len(groups) != 215 or prior_cells != set(groups):
        raise ValueError("Original expanded cell identities not restored")
    previous_exclusions = read_json(EVIDENCE / "expanded-quality.json")["exclusions"]
    if len(previous_exclusions) != 385:
        raise ValueError("Original exclusion record mismatch")

    def cell(group):
        budget.check()
        row = group[0]
        # Existing acquisition uses per-object locks, hashes and HTTP bounds.
        soil, soil_sources = acquire_soil(row["latitude"], row["longitude"], ROOT / "environment")
        power, climate = acquire_power(row["latitude"], row["longitude"], ROOT / "environment")
        features = {**power, **soil}
        for r in group:
            validate_features({**features, "crop": r["crop"], "scenario": r["scenario"]})
        return [{**r, **features, "period": PERIOD, "climate_evidence": climate,
                 "soil_evidence": soil_sources} for r in group]

    rows = []
    # Four bounded cell workers; never repeat the 385 previously excluded cells.
    with ThreadPoolExecutor(max_workers=4) as pool:
        for i, records in enumerate(pool.map(cell, groups.values()), 1):
            rows.extend(records)
            write_json(output / "progress.json", {
                "completed_locations": i, "total_locations": 215,
                "remaining_locations": 215-i, "updated_at": now(),
                "elapsed_seconds": time.monotonic()-started,
                "purpose": "restore original retained source identities; no new sample or final-test inference"})
            print(f"restored_locations={i}/215 elapsed={time.monotonic()-started:.1f}s", flush=True)
            budget.check()
    bundle = {"contract": CONTRACT, "target": TARGET, "source_manifest": samples["source_manifest"],
              "samples_sha256": sha256(ROOT / "expanded-samples.json"),
              "sampling": {k: samples[k] for k in ("seed", "requested_cells", "sampling")},
              "records": rows, "exclusions": previous_exclusions}
    bundle["dataset_hash"] = digest(bundle)
    write_json(output / "dataset.json", bundle)
    write_json(output / "quality.json", quality_report(bundle))
    write_json(output / "restoration.json", {
        "original_dataset_hash": old["dataset_hash"], "restored_dataset_hash": bundle["dataset_hash"],
        "original_cell_membership_verified": True, "label_bytes_verified": True,
        "previous_exclusions_preserved_not_reacquired": 385, "final_test_evaluated": False,
        "provenance_note": "Fresh acquisition timestamps may change dataset identity; no old hash is forged.",
        "elapsed_seconds": time.monotonic()-started})


if __name__ == "__main__":
    restore()
