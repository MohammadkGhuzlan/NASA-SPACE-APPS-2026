"""Preregistered target-independent geographic supplementation of the pilot."""
from .common import digest, read_json, write_json, sha256
from .labels import sample_labels, import_labels, validate_samples
from .spatial import block, partition, near


def supplement(samples_path, output):
    original = read_json(samples_path)
    manifest = original["source_manifest"]
    from pathlib import Path
    verified = import_labels(Path(manifest["rasters"][0]["path"]).parent)
    if digest(verified) != original["source_manifest_hash"]:
        raise ValueError("Original source manifest changed")
    validate_samples(verified, original["records"])
    candidates = sample_labels(verified, count=1200, seed=43)
    old_cells = {r["cell_id"]: r for r in original["records"]}
    grouped = {}
    for record in candidates["records"]:
        grouped.setdefault(record["cell_id"], []).append(record)
    quotas = {"test": 60, "train": 40, "validation": 20}
    selected, counts = [], {k: 0 for k in quotas}
    used_points = [(r["longitude"], r["latitude"]) for r in old_cells.values()]
    for cell_id, rows in grouped.items():
        if cell_id in old_cells:
            continue
        row = rows[0]
        assignment = partition(block(row["latitude"], row["longitude"]), 42)
        if counts[assignment] >= quotas[assignment]:
            continue
        point = (row["longitude"], row["latitude"])
        if any(near(point, other, 150) for other in used_points):
            continue
        selected.extend(rows)
        used_points.append(point)
        counts[assignment] += 1
        if counts == quotas:
            break
    if counts != quotas:
        raise ValueError(f"Candidate geography did not meet fixed quotas: {counts}")
    result = {
        **original, "requested_cells": len(old_cells) + sum(quotas.values()),
        "records": original["records"] + selected,
        "sampling": original["sampling"] + (
            "\nPreregistered supplement: independent candidate seed 43, pool 1200; "
            "test/train/validation quotas 60/40/20 using split seed 42; "
            "150 km and coarse-footprint spacing from all original/chosen cells; "
            "no selection on label magnitude, soil availability or model error."
        ),
        "supplement_protocol": {
            "original_samples_sha256": sha256(samples_path), "candidate_seed": 43,
            "candidate_cells": 1200, "partition_seed": 42, "partition_quotas": quotas,
            "minimum_separation_km": 150,
            "protocol": "docs/phase4/SUPPLEMENT_PROTOCOL.md",
        },
    }
    write_json(output, result)
    return {"planned_cells": result["requested_cells"], "additional_cells": sum(counts.values()),
            "quotas": counts, "out": str(output)}
