"""Official RES05 catalog selection, metadata validation and authentic cell sampling."""
from pathlib import Path
from urllib.parse import quote

import numpy as np
import pandas as pd
import rasterio
from pyproj import Transformer

from .common import read_json, sha256, write_json, digest
from .contract import CROPS, SCENARIO, PERIOD, coordinates
from .download import download

CATALOG_URL = "https://data.apps.fao.org/catalog/dataset/514c92d5-9e01-4c70-814a-80ea1ca9fe6a/resource/768b08ad-be9c-427a-84be-3a3d6dd7835a/download/_readme_res05.xlsx"
METADATA_URL = "https://data.apps.fao.org/catalog/api/3/action/package_show?id=d666d360-0e3c-467c-beb0-29ad55df5855"
BASE_URL = "https://storage.googleapis.com/fao-gismgr-gaez-v5-data/DATA/GAEZ-V5/MAPSET"
MAPSET = "RES05-SXX"


def catalog_selection(path):
    """Require official dimension meanings, never infer semantics from filenames alone."""
    expected = {
        "CODES_VARIABLE": ("RES05-SXX", "Suitability index"),
        "CODES_PERIOD": ("HP0120", "2001-2020"),
        "CODES_CLIMATE_DATA_SOURCE": ("AGERA5", "AgERA5"),
        "CODES_SSP": ("HIST", "Historical"),
        "CODES_WATER_INPUT": ("LRLM", "Rain-fed and low input"),
    }
    for sheet, (code, meaning) in expected.items():
        table = pd.read_excel(path, sheet, dtype=str).fillna("")
        rows = table[table.iloc[:, 0].str.strip() == code]
        if len(rows) != 1 or meaning not in rows.iloc[0, 1]:
            raise ValueError(f"Unverified catalog semantics: {sheet}/{code}")
    crops = pd.read_excel(path, "CODES_CROP", dtype=str)
    for code, name in CROPS.items():
        match = crops[crops.iloc[:, 0] == code]
        if len(match) != 1 or match.iloc[0, 1].strip() != name:
            raise ValueError(f"Crop equivalent not verified: {code}")
    raw = pd.read_excel(path, "LIST_FILES", header=None, dtype=str).fillna("")
    required = {"MAPSET_CODE", "PERIOD", "CLIMATE_DATA_SOURCE", "SSP", "CROP", "INPUT", "FILE_NAME"}
    for i in range(min(40, len(raw))):
        headers = [str(v).strip().upper().replace(" ", "_") for v in raw.iloc[i]]
        if required.issubset(headers):
            table = raw.iloc[i+1:].copy()
            table.columns = headers
            break
    else:
        raise ValueError("Missing LIST_FILES header")
    selected = table[(table.MAPSET_CODE == MAPSET) & (table.PERIOD == "HP0120") &
                     (table.CLIMATE_DATA_SOURCE == "AGERA5") & (table.SSP == "HIST") &
                     (table.INPUT == SCENARIO) & table.CROP.isin(CROPS)]
    if len(selected) != len(CROPS) or set(selected.CROP) != set(CROPS):
        raise ValueError("Incomplete or duplicate crop/scenario selection")
    return selected[list(sorted(required))].to_dict("records")


def verify_metadata(payload):
    body = payload["result"]["jsonschema_body"]
    info = body["dataIdentification"]
    supplemental = info["supplementalInformation"]
    if not all(s in supplemental for s in ("RES05-SXX", "10000", "-9", "1.0", "Index")):
        raise ValueError("Unverified suitability scale/NoData")
    if body["referenceSystemIdentifier"] != "EPSG:4326 - WGS84":
        raise ValueError("Unverified CRS")
    if payload["result"]["license_id"] != "CC-BY-4.0":
        raise ValueError("License requires explicit review")
    if not np.isclose(float(info["spatialResolution"][0]["distance"]), 1/12):
        raise ValueError("Unexpected source resolution")
    return body


def raster_metadata(path):
    with rasterio.open(path) as src:
        if (src.crs != rasterio.crs.CRS.from_epsg(4326) or src.count != 1 or
                src.nodata != -9 or src.dtypes != ("int16",) or
                not np.allclose(src.res, [1/12, 1/12]) or
                src.width != 4320 or src.height != 2160 or
                not np.allclose(tuple(src.bounds), [-180, -90, 180, 90]) or
                src.scales != (1.0,) or src.offsets != (0.0,)):
            raise ValueError("Raster contradicts verified GAEZ grid metadata")
        values = src.read(1, masked=True).compressed()
        if not len(values) or np.any((values < 0) | (values > 10000)):
            raise ValueError("Invalid suitability values")
        return {"crs": str(src.crs), "transform": list(src.transform),
                "shape": [src.height, src.width], "resolution_degrees": list(src.res),
                "nodata": src.nodata, "valid_cells": len(values)}


def import_labels(root):
    """Also validates manually supplied files against acquisition sidecars."""
    root = Path(root)
    verify_metadata(read_json(root / "metadata.json"))
    meta_evidence = read_json(root / "metadata.json.source.json")
    cat_evidence = read_json(root / "catalog.xlsx.source.json")
    for path, evidence, url in [(root / "metadata.json", meta_evidence, METADATA_URL),
                                (root / "catalog.xlsx", cat_evidence, CATALOG_URL)]:
        if evidence["sha256"] != sha256(path) or evidence["url"] != url:
            raise ValueError("Metadata/catalog provenance mismatch")
    records = []
    for row in catalog_selection(root / "catalog.xlsx"):
        name = row["FILE_NAME"].removesuffix(".tif") + ".tif"
        url = f"{BASE_URL}/{MAPSET}/{quote(name)}"
        path = root / name
        evidence = read_json(path.with_suffix(".tif.source.json"))
        if evidence["url"] != url or evidence["sha256"] != sha256(path):
            raise ValueError("Label provenance/hash mismatch")
        records.append({"crop": row["CROP"], "path": str(path),
                        "catalog_row": row, **evidence, **raster_metadata(path)})
    manifest = {"publisher": "FAO / IIASA", "version": "GAEZ v5", "license": "CC-BY-4.0",
                "attribution": "FAO and IIASA (2025), GAEZ v5 suitability index; subset/processing by Field Shift",
                "mapset": MAPSET, "period": PERIOD, "scenario": SCENARIO,
                "catalog": cat_evidence, "metadata": meta_evidence, "rasters": records}
    write_json(root / "manifest.json", manifest)
    return manifest


def acquire_labels(root):
    root = Path(root)
    download(CATALOG_URL, root / "catalog.xlsx", max_bytes=8_000_000)
    download(METADATA_URL, root / "metadata.json")
    verify_metadata(read_json(root / "metadata.json"))
    for row in catalog_selection(root / "catalog.xlsx"):
        name = row["FILE_NAME"].removesuffix(".tif") + ".tif"
        download(f"{BASE_URL}/{MAPSET}/{quote(name)}", root / name)
    return import_labels(root)


def validate_samples(manifest, records):
    """Reject changed/duplicated sample values before expensive acquisition."""
    handles = {}
    seen = set()
    try:
        handles = {r["crop"]: rasterio.open(r["path"]) for r in manifest["rasters"]}
        hashes = {r["crop"]: r["sha256"] for r in manifest["rasters"]}
        for row in records:
            crop = row["crop"]
            if crop not in handles or row["scenario"] != SCENARIO:
                raise ValueError("Unsupported label crop/scenario")
            src = handles[crop]
            rr, cc = cell_at(src, row["latitude"], row["longitude"])
            lon, lat = src.xy(rr, cc)
            key = (row["cell_id"], crop)
            if key in seen:
                raise ValueError("Duplicate sampled source cell/crop")
            seen.add(key)
            value = src.read(1, window=((rr, rr+1), (cc, cc+1)), masked=True)[0, 0]
            if (np.ma.is_masked(value) or int(value) != row["target"] or
                    row["cell_id"] != f"{MAPSET}:{rr}:{cc}" or
                    row["label_sha256"] != hashes[crop] or
                    row["row"] != rr or row["col"] != cc or
                    abs(lon-row["longitude"]) > 1e-8 or abs(lat-row["latitude"]) > 1e-8):
                raise ValueError("Sample does not match original label identity/value")
    finally:
        for handle in handles.values():
            handle.close()
    return True


def cell_at(src, lat, lon):
    coordinates(lat, lon)
    x, y = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True).transform(lon, lat)
    row, col = src.index(x, y)
    if not 0 <= row < src.height or not 0 <= col < src.width:
        raise ValueError("outside_source_extent")
    return row, col


def sample_labels(manifest, count=240, seed=42):
    """Uniform seeded valid-cell sample, round-robin 20° strata; no target balancing.

    Retains zero suitability. One candidate per conservative 1.5° footprint
    reduces redundant climate requests; counts are not independence claims.
    """
    rng = np.random.default_rng(seed)
    sources = [rasterio.open(r["path"]) for r in manifest["rasters"]]
    try:
        arrays = [s.read(1, masked=True) for s in sources]
        valid = np.logical_and.reduce([~np.ma.getmaskarray(a) for a in arrays])
        rows, cols = np.where(valid)
        order = rng.permutation(len(rows))
        strata = {}
        used = set()
        for index in order[:max(count * 200, 20000)]:
            r, c = int(rows[index]), int(cols[index])
            lon, lat = sources[0].xy(r, c)
            if not -60 < lat < 75:
                continue
            footprint = (int((lat + 90) // 1.5), int((lon + 180) // 1.5))
            if footprint in used:
                continue
            used.add(footprint)
            key = (int((lat+90)//20), int((lon+180)//20))
            strata.setdefault(key, []).append((r, c, lat, lon))
        chosen = []
        keys = sorted(strata)
        rng.shuffle(keys)
        while len(chosen) < count and any(strata.values()):
            for key in keys:
                if strata[key] and len(chosen) < count:
                    chosen.append(strata[key].pop())
        result = []
        for r, c, lat, lon in chosen:
            cell = f"{MAPSET}:{r}:{c}"
            for i, source in enumerate(manifest["rasters"]):
                result.append({"latitude": lat, "longitude": lon, "row": r, "col": c,
                               "cell_id": cell, "crop": source["crop"], "scenario": SCENARIO,
                               "target": int(arrays[i][r, c]), "label_sha256": source["sha256"]})
        return {"seed": seed, "requested_cells": count, "sampling": sample_labels.__doc__,
                "source_manifest_hash": digest(manifest), "source_manifest": manifest,
                "records": result}
    finally:
        for src in sources:
            src.close()
