"""Exact containing-cell reads of verified local categorical rasters; no interpolation."""
from functools import lru_cache
import math
from pathlib import Path

from pyproj import Transformer
import rasterio
from rasterio.windows import Window, bounds

from ..machine_learning.common import sha256
from .catalog import ROOT, DATASET, CROPS, SCENARIOS, CLASSES, SourceUnavailable, read_manifest


@lru_cache(maxsize=64)
def verified_file(path, size, mtime_ns, expected_hash):
    if sha256(Path(path)) != expected_hash:
        raise SourceUnavailable("Raster checksum differs from acquired source.")
    return True


def read_cell(src, latitude, longitude):
    x, y = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True).transform(longitude, latitude)
    row, col = src.index(x, y)
    if not (0 <= row < src.height and 0 <= col < src.width):
        return {"status": "outside_coverage", "rawValue": None, "category": None, "sampling": {}}
    pixel = src.read(1, window=Window(col, row, 1, 1), masked=True)[0, 0]
    cx, cy = src.xy(row, col)
    cl, ct = Transformer.from_crs(src.crs, "EPSG:4326", always_xy=True).transform(cx, cy)
    spatial = {"method": "containing raster cell; nearest-neighbor, no interpolation",
               "latitude": latitude, "longitude": longitude, "row": row, "column": col,
               "cellCenterLatitude": ct, "cellCenterLongitude": cl,
               "cellBounds": list(bounds(Window(col, row, 1, 1), src.transform)),
               "cellBoundsCrs": str(src.crs)}
    if bool(getattr(pixel, "mask", False)):
        return {"status": "nodata", "rawValue": None, "category": None, "sampling": spatial}
    value = int(pixel)
    if value not in CLASSES:
        raise SourceUnavailable("Unrecognized class code; interpretation refused.")
    return {"status": "nodata" if value == 0 else "not_land" if value == 9 else "available",
            "rawValue": value, "category": CLASSES[value], "sampling": spatial}


def assess(latitude, longitude, crop_code, scenario, *, version="GAEZ-v5", period="2001-2020",
           root=None, manifest=None):
    if (not math.isfinite(latitude) or not math.isfinite(longitude)
            or not -90 <= latitude <= 90 or not -180 <= longitude <= 180):
        raise ValueError("Invalid WGS84 coordinates.")
    evidence = {"cropCode": crop_code, "cropName": CROPS.get(crop_code, crop_code),
                "scenario": scenario, "scenarioLabel": SCENARIOS.get(scenario, scenario),
                "dataset": DATASET, "datasetId": None, "sourceUrl": None, "sha256": None,
                "retrievedAt": None, "rawValue": None, "category": None, "sampling": {},
                "warnings": ["Published modeled assessment, not observed farm yield or harvest probability.",
                             "Single coarse raster cell, not an area-weighted farm-boundary or soil-test assessment."]}
    if crop_code not in CROPS or scenario not in SCENARIOS or version != "GAEZ-v5" or period != "2001-2020":
        return {**evidence, "status": "unsupported", "warnings": [*evidence["warnings"], "Crop/scenario/version/period is outside the verified subset."]}
    root = Path(root or ROOT)
    try:
        m = manifest or read_manifest(root)
        asset = next((a for a in m["assets"] if a["cropCode"] == crop_code and a["scenario"] == scenario), None)
        if asset is None:
            raise SourceUnavailable("Requested verified layer has not been acquired.")
        path = root / asset["file"]
        stat = path.stat()
        verified_file(str(path), stat.st_size, stat.st_mtime_ns, asset["sha256"])
        with rasterio.Env(GDAL_CACHEMAX=16 * 1024 * 1024):
            with rasterio.open(path) as src:
                if str(src.crs) != "EPSG:4326" or src.nodata != 0 or src.dtypes != ("uint8",):
                    raise SourceUnavailable("Raster contract changed.")
                cell = read_cell(src, latitude, longitude)
        return {**evidence, **cell, "datasetId": asset["file"].removesuffix(".tif"),
                "sourceUrl": asset["url"], "sha256": asset["sha256"], "retrievedAt": asset["retrieved_at"]}
    except SourceUnavailable as exc:
        return {**evidence, "status": "unavailable",
                "warnings": [*evidence["warnings"], str(exc)]}
    except (OSError, rasterio.errors.RasterioError):
        return {**evidence, "status": "unavailable",
                "warnings": [*evidence["warnings"], "Verified raster cache cannot be read; authorized operator ingestion or repair is required."]}
