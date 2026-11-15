"""Closed, bounded GAEZ RES05-SIX catalog. Never accept user-supplied URLs."""
import json
from pathlib import Path

from ..machine_learning.common import sha256

ROOT = Path(__file__).resolve().parents[4] / "generated-artifacts/gaez-evidence"
CATALOG_URL = "https://data.apps.fao.org/catalog/dataset/514c92d5-9e01-4c70-814a-80ea1ca9fe6a/resource/768b08ad-be9c-427a-84be-3a3d6dd7835a/download/_readme_res05.xlsx"
METADATA_URL = "https://data.apps.fao.org/catalog/api/3/action/package_show?id=514c92d5-9e01-4c70-814a-80ea1ca9fe6a"
STYLE_URL = "https://data.apps.fao.org/gismgr/api/v2/catalog/workspaces/GAEZ-V5/styles/SIX/sld"
BASE = "https://storage.googleapis.com/fao-gismgr-gaez-v5-data/DATA/GAEZ-V5/MAPSET/RES05-SIX/"
CROPS = {"WHE": "Wheat", "BRL": "Barley", "MZE": "Maize", "SOY": "Soybean",
         "CHK": "Chickpea", "RCD": "Dryland rice", "RCW": "Wetland rice"}
SCENARIOS = {"LRLM": "Rain-fed and low input level of management",
             "HRLM": "Rain-fed and high input level of management",
             "LILM": "Irrigation and low input level of management",
             "HILM": "Irrigation and high input level of management"}
CLASSES = {0: "no data", 1: "SI >85 : Very high", 2: "SI >70 : High",
           3: "SI >55 : Good", 4: "SI >40 : Medium", 5: "SI >25 : Moderate",
           6: "SI >10 : Marginal", 7: "SI >0 : Very marginal",
           8: "Not suitable", 9: "Water"}
DATASET = {
    "version": "GAEZ-v5", "variable": "RES05-SIX", "referencePeriod": "2001-2020",
    "title": "Crop suitability, class index (Global - 20 years average - ~10 km) - GAEZ v5",
    "climateSource": "AgERA5", "crs": "EPSG:4326",
    "resolutionDegrees": 1 / 12, "resolutionLabel": "5 arc minutes (approximately 10 km at equator)",
    "unit": "categorical class code; not a probability or percentage",
    "noData": 0, "dtype": "uint8", "license": "CC-BY-4.0",
    "metadataUrl": METADATA_URL, "catalogUrl": CATALOG_URL, "classDefinitionUrl": STYLE_URL,
    "attribution": "FAO and IIASA (2025), GAEZ v5. Class-raster point extraction by Field Shift; no endorsement.",
}


class SourceUnavailable(ValueError):
    pass


def read_manifest(root=None):
    root = Path(root or ROOT)
    try:
        manifest = json.loads((root / "manifest.json").read_text())
        if manifest["dataset"] != DATASET:
            raise SourceUnavailable("Cached dataset contract differs from verified RES05-SIX metadata.")
        for name in ("catalog.xlsx", "six-metadata.json", "six-definition.json", "six-style.sld"):
            evidence = manifest["sources"][name]
            if sha256(root / name) != evidence["sha256"]:
                raise SourceUnavailable("Cached official metadata checksum mismatch.")
        for asset in manifest["assets"]:
            row = asset["catalogRow"]
            if (asset["cropCode"] not in CROPS or asset["scenario"] not in SCENARIOS
                    or Path(asset["file"]).name != asset["file"]
                    or asset["url"] != BASE + asset["file"]
                    or row["CROP"] != asset["cropCode"] or row["INPUT"] != asset["scenario"]
                    or row["MAPSET_CODE"] != "RES05-SIX" or row["PERIOD"] != "HP0120"
                    or row["CLIMATE_DATA_SOURCE"] != "AGERA5" or row["SSP"] != "HIST"
                    or row["FILE_NAME"].removesuffix(".tif") + ".tif" != asset["file"]):
                raise SourceUnavailable("Unrecognized asset identity.")
        pairs = [(a["cropCode"], a["scenario"]) for a in manifest["assets"]]
        if len(pairs) != 28 or set(pairs) != {(c, s) for c in CROPS for s in SCENARIOS}:
            raise SourceUnavailable("Incomplete or duplicated verified catalog.")
        return manifest
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise SourceUnavailable("Verified FAO cache is absent or incomplete; authorized ingestion is required.") from exc


def catalog_status():
    try:
        m = read_manifest()
        available = {(a["cropCode"], a["scenario"]) for a in m["assets"] if (ROOT / a["file"]).is_file()}
        status = "available" if len(available) == 28 else "unavailable"
        warning = [] if len(available) == 28 else ["Selected raster cache is incomplete; individual missing layers remain unavailable."]
    except SourceUnavailable as exc:
        available, status, warning = set(), "unavailable", [str(exc)]
    return {"status": status, "dataset": DATASET, "warnings": warning,
            "crops": [{"code": c, "name": n} for c, n in CROPS.items()],
            "scenarios": [{"code": c, "name": n} for c, n in SCENARIOS.items()],
            "classes": [{"code": c, "label": n} for c, n in CLASSES.items()],
            "cachedLayers": len(available)}
