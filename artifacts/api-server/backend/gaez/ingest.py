"""Explicit operator CLI: resolve official catalog rows, then acquire only 28 small layers."""
import json
import fcntl
import re
import xml.etree.ElementTree as ET

import httpx
import numpy as np
import openpyxl
import rasterio

from ..machine_learning.download import download
from ..machine_learning.common import write_json
from .catalog import (ROOT, CATALOG_URL, METADATA_URL, STYLE_URL, BASE, CROPS,
                      SCENARIOS, CLASSES, DATASET)


def validate_raster(path):
    with rasterio.open(path) as src:
        if (str(src.crs) != "EPSG:4326" or src.shape != (2160, 4320)
                or src.dtypes != ("uint8",) or src.count != 1 or src.nodata != 0
                or not np.allclose(src.res, (1 / 12, 1 / 12))
                or not np.allclose(tuple(src.bounds), (-180, -90, 180, 90))):
            raise ValueError("Raster header contradicts verified SIX contract.")
        values = src.read(1)
        if not np.isin(values, list(CLASSES)).all():
            raise ValueError("Unknown categorical raster code.")
        return {"crs": str(src.crs), "shape": list(src.shape),
                "bounds": list(src.bounds), "dtype": src.dtypes[0], "noData": src.nodata}


def _acquire(root):
    root.mkdir(parents=True, exist_ok=True)
    sources = {}
    for name, url in [("catalog.xlsx", CATALOG_URL), ("six-metadata.json", METADATA_URL)]:
        sources[name] = download(url, root / name, max_bytes=8_000_000)
    metadata = json.loads((root / "six-metadata.json").read_text())["result"]
    if metadata["title"] != DATASET["title"] or metadata["license_id"] != DATASET["license"]:
        raise ValueError("Official identity/license changed; re-review required.")
    resources = metadata["resources"]
    # Resolve both authoritative definitions from the actual dataset metadata.
    definition_url = next(r["url"] for r in resources if r.get("name") == "RES05-SIX")
    if definition_url != "https://data.apps.fao.org/catalog/dataset/514c92d5-9e01-4c70-814a-80ea1ca9fe6a/resource/e69258af-55e4-49e3-a749-3e5a38c49244/download/res05.json":
        raise ValueError("Dataset-definition identity changed.")
    if not any(r.get("url") == STYLE_URL for r in resources):
        raise ValueError("Official class-definition resource absent.")
    for name, url in [("six-definition.json", definition_url), ("six-style.sld", STYLE_URL)]:
        sources[name] = download(url, root / name, max_bytes=1_000_000)
    doc = ET.parse(root / "six-style.sld")
    classes = {int(float(e.attrib["quantity"])): e.attrib["label"]
               for e in doc.iter() if e.tag.endswith("ColorMapEntry")}
    if classes != CLASSES:
        raise ValueError("Official class definitions changed; do not guess interpretation.")
    workbook = openpyxl.load_workbook(root / "catalog.xlsx", read_only=True, data_only=True)
    for sheet, expected in [("CODES_CROP", CROPS), ("CODES_WATER_INPUT", SCENARIOS),
                             ("CODES_PERIOD", {"HP0120": "2001-2020"}),
                             ("CODES_VARIABLE", {"RES05-SIX": "Crop suitability index in classes; all land in grid cell"})]:
        mapping = {r[0]: r[1] for r in list(workbook[sheet].values)[1:] if r[0]}
        if any(mapping.get(k) != v for k, v in expected.items()):
            raise ValueError("Official crop/scenario/variable mapping changed.")
    rows = iter(workbook["LIST_FILES"].values)
    headers = next(rows)
    selected = []
    for values in rows:
        row = dict(zip(headers, values))
        if (row["MAPSET_CODE"] == "RES05-SIX" and row["PERIOD"] == "HP0120"
                and row["CLIMATE_DATA_SOURCE"] == "AGERA5" and row["SSP"] == "HIST"
                and row["CROP"] in CROPS and row["INPUT"] in SCENARIOS):
            selected.append(row)
    workbook.close()
    if len(selected) != 28 or len({(r["CROP"], r["INPUT"]) for r in selected}) != 28:
        raise ValueError("Expected verified crop/scenario combinations are missing or duplicated.")
    assets, total = [], 0
    for row in selected:
        name = row["FILE_NAME"].removesuffix(".tif") + ".tif"
        if not re.fullmatch(r"GAEZ-V5\.RES05-SIX\.HP0120\.AGERA5\.HIST\.[A-Z]{3}\.[A-Z]{4}\.tif", name):
            raise ValueError("Unsafe catalog filename.")
        # Metadata/stat requests are bounded; acquisition is serialized by the
        # downloader's per-asset lock, size limit and resumable .part file.
        response = httpx.head(BASE + name, timeout=20)
        response.raise_for_status()
        size = int(response.headers.get("content-length", 0))
        if size <= 0 or size > 5_000_000 or total + size > 40_000_000:
            raise ValueError("Selected raster budget exceeded; operator review needed.")
        evidence = download(BASE + name, root / name, max_bytes=5_000_000)
        total += evidence["bytes"]
        assets.append({"cropCode": row["CROP"], "scenario": row["INPUT"], "file": name,
                       "catalogRow": row, **evidence, "header": validate_raster(root / name)})
    manifest = {"dataset": DATASET, "sources": sources, "assets": assets,
                "bytes": total, "classes": classes, "acquisition": "official catalog-resolved, complete selected GeoTIFFs"}
    # Atomic publication: an interrupted acquisition cannot expose half a catalog.
    temp = root / "manifest.json.part"
    write_json(temp, manifest)
    temp.replace(root / "manifest.json")
    return manifest


def acquire(root=ROOT):
    root.mkdir(parents=True, exist_ok=True)
    with (root / ".ingestion.lock").open("a") as lock:
        # One acquisition per cache, not one large download per public request.
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return _acquire(root)


if __name__ == "__main__":
    m = acquire()
    print(json.dumps({"layers": len(m["assets"]), "rasterBytes": m["bytes"],
                      "dataset": m["dataset"]}, indent=2))
