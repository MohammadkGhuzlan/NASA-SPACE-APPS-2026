"""File-based preparation, replay validation and explicit exclusion reports."""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

from .common import digest, read_json, write_json, sha256
from .contract import CONTRACT, FEATURES, PERIOD, TARGET, validate_features, coordinates
from .environment import acquire_power, acquire_soil
from .labels import import_labels, cell_at, validate_samples


def prepare(samples_path, cache, output):
    samples = read_json(samples_path)
    # Verify immutable scientific sources again before any environmental requests.
    manifest = samples["source_manifest"]
    root = Path(manifest["rasters"][0]["path"]).parent
    if digest(import_labels(root)) != samples["source_manifest_hash"]:
        raise ValueError("Label manifest changed since sampling")
    validate_samples(manifest, samples["records"])
    cells = {}
    for row in samples["records"]:
        cells.setdefault(row["cell_id"], []).append(row)

    def process(group):
        row = group[0]
        try:
            # Soil masks exclude many all-land cells. Check them before fetching
            # a complete 20-year weather series that could not be used.
            soil, soil_sources = acquire_soil(row["latitude"], row["longitude"], cache)
            power, climate = acquire_power(row["latitude"], row["longitude"], cache)
            features = {**power, **soil}
            for r in group:
                validate_features({**features, "crop": r["crop"], "scenario": r["scenario"]})
            return [{**r, **features, "period": PERIOD, "climate_evidence": climate,
                     "soil_evidence": soil_sources} for r in group], None
        except (ValueError, OSError, KeyError, TypeError, RuntimeError) as exc:
            return [], {"cell_id": row["cell_id"], "reason": str(exc), "excluded_rows": len(group)}
        except Exception as exc:
            # HTTP and raster parsing failures are scientific exclusions, never substitutions.
            return [], {"cell_id": row["cell_id"], "reason": f"{type(exc).__name__}: {exc}",
                        "excluded_rows": len(group)}

    rows, exclusions = [], []
    with ThreadPoolExecutor(max_workers=2) as pool:
        for index, (valid, failure) in enumerate(pool.map(process, cells.values()), 1):
            rows.extend(valid)
            if failure:
                exclusions.append(failure)
            # Incremental reports make interrupted runs inspectable; cache makes restart cheap.
            write_json(Path(output) / "progress.json", {"processed_cells": index,
                       "total_cells": len(cells), "valid_rows": len(rows), "excluded": exclusions})
    bundle = {"contract": CONTRACT, "target": TARGET, "source_manifest": manifest,
              "samples_sha256": sha256(samples_path), "sampling": {
                  k: samples[k] for k in ("seed", "requested_cells", "sampling")},
              "records": rows, "exclusions": exclusions}
    bundle["dataset_hash"] = digest(bundle)
    write_json(Path(output) / "dataset.json", bundle)
    report = quality_report(bundle)
    write_json(Path(output) / "quality.json", report)
    return report


def quality_report(bundle):
    rows = bundle["records"]
    frame = pd.DataFrame(rows)
    report = {
        "source_records": len(rows) + sum(x["excluded_rows"] for x in bundle["exclusions"]),
        "final_examples": len(rows), "effective_label_cells": len({r["cell_id"] for r in rows}),
        "excluded_rows": sum(x["excluded_rows"] for x in bundle["exclusions"]),
        "exclusions": bundle["exclusions"], "missing_policy": "complete-case rejection, no imputation",
        "period": PERIOD, "dataset_hash": bundle["dataset_hash"],
        "crop_counts": dict(Counter(r["crop"] for r in rows)),
        "source_hashes": [r["sha256"] for r in bundle["source_manifest"]["rasters"]],
        "independence_notice": "Rows repeated across crops are not independent environmental observations",
    }
    if rows:
        cells = {r["cell_id"]: r for r in rows}
        # Connected components under conservative shared-footprint envelopes:
        # this is a lower-resolution effective coverage diagnostic, not an
        # assertion that nearby climates are statistically independent.
        from .spatial import near
        parent = {key: key for key in cells}

        def find(key):
            while parent[key] != key:
                parent[key] = parent[parent[key]]
                key = parent[key]
            return key

        keys = list(cells)
        for i, key in enumerate(keys):
            a = cells[key]
            for other in keys[i+1:]:
                b = cells[other]
                if near((a["longitude"], a["latitude"]), (b["longitude"], b["latitude"]), 0):
                    parent[find(key)] = find(other)
        report.update(
            effective_coarse_environment_groups=len({find(key) for key in keys}),
            extent={k: [float(frame[k].min()), float(frame[k].max())] for k in ("latitude", "longitude")},
            label_distribution={crop: {"count": len(g), "min": float(g.target.min()),
                                      "max": float(g.target.max()), "mean": float(g.target.mean()),
                                      "zero_count": int((g.target == 0).sum())}
                                for crop, g in frame.groupby("crop")},
            missing_rates={k: float(frame[k].isna().mean()) for k in FEATURES},
            geographic_20deg_counts=dict(Counter(
                f"{int((r['latitude']+90)//20)}:{int((r['longitude']+180)//20)}"
                for r in {r["cell_id"]: r for r in rows}.values())),
        )
    return report


def validate_dataset(bundle, *, replay=True):
    claimed = bundle["dataset_hash"]
    if digest({k: v for k, v in bundle.items() if k != "dataset_hash"}) != claimed:
        raise ValueError("Dataset hash mismatch")
    if bundle["contract"] != CONTRACT or bundle["target"] != TARGET:
        raise ValueError("Dataset contract mismatch")
    manifest = bundle["source_manifest"]
    if replay:
        if digest(import_labels(Path(manifest["rasters"][0]["path"]).parent)) != digest(manifest):
            raise ValueError("Source replay mismatch")
    seen = set()
    import rasterio
    rasters = {}
    checked_environments = {}
    try:
        if replay:
            rasters = {r["crop"]: rasterio.open(r["path"]) for r in manifest["rasters"]}
        for row in bundle["records"]:
            coordinates(row["latitude"], row["longitude"])
            validate_features({k: row[k] for k in FEATURES})
            if row["period"] != PERIOD or not np.isfinite(row["target"]) or not 0 <= row["target"] <= 10000:
                raise ValueError("Invalid target or reference period")
            key = (row["cell_id"], row["crop"], row["scenario"])
            if key in seen:
                raise ValueError("Duplicate source cell/crop/scenario")
            seen.add(key)
            if replay:
                src = rasters[row["crop"]]
                rr, cc = cell_at(src, row["latitude"], row["longitude"])
                lon, lat = src.xy(rr, cc)
                source = next(r for r in manifest["rasters"] if r["crop"] == row["crop"])
                if (row["cell_id"] != f"RES05-SXX:{rr}:{cc}" or
                        row["label_sha256"] != source["sha256"] or
                        abs(lon-row["longitude"]) > 1e-8 or abs(lat-row["latitude"]) > 1e-8 or
                        src.read(1, window=((rr, rr+1), (cc, cc+1)))[0, 0] != row["target"]):
                    raise ValueError("Label identity/value mismatch")
                environment_hash = digest({
                    "values": {k: row[k] for k in FEATURES if k not in {"crop", "scenario"}},
                    "climate": row["climate_evidence"], "soil": row["soil_evidence"],
                })
                if row["cell_id"] in checked_environments:
                    if checked_environments[row["cell_id"]] != environment_hash:
                        raise ValueError("Inconsistent environment for repeated source cell")
                    continue
                # Recompute environmental values from hash-verified original responses.
                from .environment import power_features, native_soil_mean, SOIL_PROPERTIES
                from urllib.parse import urlparse, parse_qs
                climate = row["climate_evidence"]
                if sha256(climate["path"]) != climate["sha256"] or climate["period"] != PERIOD:
                    raise ValueError("Climate provenance mismatch")
                if climate["point"] != [lon, lat]:
                    raise ValueError("Climate spatial mismatch")
                url = urlparse(climate["url"])
                params = parse_qs(url.query)
                expected_params = {
                    "parameters": ["T2M,PRECTOTCORR"], "community": ["AG"],
                    "latitude": [str(lat)], "longitude": [str(lon)],
                    "start": ["20010101"], "end": ["20201231"], "format": ["JSON"],
                    "time-standard": ["UTC"],
                }
                if (url.scheme != "https" or url.netloc != "power.larc.nasa.gov" or
                        url.path != "/api/temporal/daily/point" or params != expected_params):
                    raise ValueError("Climate source request mismatch")
                power = power_features(read_json(climate["path"]))
                for key, value in power.items():
                    if not np.isclose(value, row[key], atol=1e-8):
                        raise ValueError("Climate feature replay mismatch")
                for prop, feature in SOIL_PROPERTIES.items():
                    evidence = row["soil_evidence"][prop]
                    if sha256(evidence["path"]) != evidence["vrt_sha256"]:
                        raise ValueError("Soil provenance mismatch")
                    provenance = read_json(Path(evidence["path"]).with_suffix(".vrt.source.json"))
                    if provenance["url"] != f"https://files.isric.org/soilgrids/latest/data/{prop}/{prop}_0-5cm_mean.vrt":
                        raise ValueError("Soil product source mismatch")
                    # Verify every downloaded tile before replay; downloader reuses
                    # only hash-verified cache, never replaces an original.
                    for tile in evidence["tiles"]:
                        if sha256(tile["path"]) != tile["sha256"]:
                            raise ValueError("Soil tile provenance mismatch")
                    value, replayed = native_soil_mean(
                        evidence["path"], lat, lon, Path(evidence["path"]).parent)
                    if replayed != {k: v for k, v in evidence.items() if k != "product"}:
                        raise ValueError("Soil acquisition metadata mismatch")
                    if not np.isclose(value, row[feature], atol=1e-8):
                        raise ValueError("Soil feature replay mismatch")
                checked_environments[row["cell_id"]] = environment_hash
    finally:
        for src in rasters.values():
            src.close()
    return pd.DataFrame(bundle["records"])
