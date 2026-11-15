"""Create small factual audit and attributable real-source test fixtures."""
import csv
from collections import Counter
from pathlib import Path
from zipfile import ZipFile
import hashlib

import rasterio
from rasterio.windows import Window

from .common import read_json, write_json, sha256
from .labels import import_labels, catalog_selection

ROOT = Path(__file__).resolve().parents[4]


def capture(run_root, destination):
    run_root, destination = Path(run_root), Path(destination)
    manifest = import_labels(run_root / "labels")
    inventory = []
    archive = ROOT / "attached_assets/Field_Shift_Replit_Data_1794680523930.zip"
    with ZipFile(archive) as bundle:
        for name in ("nasa_daily.csv", "nasa_monthly.csv", "nasa_soil_moisture_daily.csv",
                     "soilgrids_0_5cm_aligned.csv"):
            path = ROOT / "data/imports" / name
            with path.open(newline="") as stream:
                reader = csv.DictReader(stream)
                rows = list(reader)
                headers = reader.fieldnames
            date_column = "date" if "date" in headers else "month" if "month" in headers else None
            inventory.append({
                "file": str(path.relative_to(ROOT)), "sha256": sha256(path),
                "archive_bytes_match": hashlib.sha256(bundle.read(name)).hexdigest() == sha256(path),
                "records": len(rows), "columns": headers,
                "locations": dict(Counter(row["location_id"] for row in rows)),
                "period": [min(row[date_column] for row in rows), max(row[date_column] for row in rows)] if date_column else None,
                "training_eligible": False,
                "reason": "2019–2025 demo inputs without suitability labels; soil proxies ineligible",
            })
    samples = read_json(run_root / "samples.json")
    # A source-derived fixture is not a training dataset.
    records = samples["records"][:25]
    fixture_dir = ROOT / "artifacts/api-server/tests/fixtures/phase4"
    fixture_dir.mkdir(parents=True, exist_ok=True)
    fixture = {"kind": "AUTHENTIC_SOURCE_SUBSET_NOT_TRAINING_DATA",
               "attribution": manifest["attribution"], "license": manifest["license"],
               "period": manifest["period"], "scenario": manifest["scenario"],
               "source_manifest": manifest, "records": records}
    write_json(fixture_dir / "gaez_cells.json", fixture)
    source = next(r for r in manifest["rasters"] if r["crop"] == "BRL")
    sample = records[0]
    with rasterio.open(source["path"]) as src:
        window = Window(sample["col"]-1, sample["row"]-1, 3, 3)
        profile = src.profile.copy()
        profile.update(width=3, height=3, transform=src.window_transform(window),
                       tiled=False, blockxsize=3, blockysize=3, compress="deflate")
        # Remove tile block settings inherited from original COG.
        profile.pop("blockxsize", None)
        profile.pop("blockysize", None)
        with rasterio.open(fixture_dir / "gaez_brl_window.tif", "w", **profile) as out:
            out.write(src.read(window=window))
    fixture["window"] = {"file": "gaez_brl_window.tif",
                         "sha256": sha256(fixture_dir / "gaez_brl_window.tif"),
                         "parent_sha256": source["sha256"],
                         "parent_window": [sample["col"]-1, sample["row"]-1, 3, 3]}
    write_json(fixture_dir / "gaez_cells.json", fixture)
    report = {"historical_files": inventory, "archive_sha256": sha256(archive),
              "labels": manifest, "selected_catalog_rows": catalog_selection(run_root / "labels/catalog.xlsx"),
              "sampled_label_rows": len(samples["records"]),
              "sampled_cells": len({r["cell_id"] for r in samples["records"]}),
              "soil_access_findings": {
                  "REST": "Two demo point probes returned null, not transferable verified soil",
                  "WCS": "GeoTIFF nodata=None; DescribeCoverage empty nilValues. Rejected instead of guessing zero mask.",
                  "WebDAV": "Native VRT explicitly declares -32768; native tile subset implementation retains masks",
              }}
    diagnostics = {}
    for name in ("res05.ipynb", "power-probe.json", "soil-probe.json", "soil-probe2.json",
                 "wcs.xml", "clay-description.xml", "wcs-clay.tif", "wcs-native.tif"):
        path = run_root / name
        if path.exists():
            item = {"file": name, "sha256": sha256(path), "bytes": path.stat().st_size}
            if name.startswith("soil-probe"):
                data = read_json(path)
                item["returned_geometry"] = data.get("geometry")
                item["returned_mean_values"] = {
                    layer["name"]: layer["depths"][0]["values"]["mean"]
                    for layer in data["properties"]["layers"]}
            elif name.endswith(".tif"):
                with rasterio.open(path) as src:
                    item.update(nodata=src.nodata, crs=str(src.crs),
                                shape=[src.height, src.width])
            diagnostics[name] = item
    report["access_diagnostics"] = diagnostics
    write_json(destination / "source-audit.json", report)
    return report
