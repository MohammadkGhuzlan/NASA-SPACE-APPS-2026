"""Independent historical acquisition; never calls the live 2019–2025 service."""
from calendar import monthrange
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlencode

import numpy as np
import rasterio

from .common import read_json, digest
from .contract import PERIOD, coordinates
from .download import download

POWER_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
SOIL_URL = "https://maps.isric.org/mapserv"
SOIL_PROPERTIES = {"clay": "clay_pct", "sand": "sand_pct", "silt": "silt_pct",
                   "phh2o": "ph", "soc": "soc_g_kg"}


def power_features(payload, period=PERIOD):
    """Require every daily value; equal-weight complete monthly totals/means over years."""
    if list(period) != PERIOD:
        raise ValueError("period_mismatch")
    if payload["header"].get("time_standard") != "UTC":
        raise ValueError("NASA_time_standard_mismatch")
    values = payload["properties"]["parameter"]
    by_month = defaultdict(list)
    start, end = date(period[0], 1, 1), date(period[1], 12, 31)
    expected = set()
    day = start
    while day <= end:
        expected.add(day.strftime("%Y%m%d"))
        day += timedelta(days=1)
    result = {}
    for key, unit in (("T2M", "C"), ("PRECTOTCORR", "mm/day")):
        if payload["parameters"][key]["units"] != unit:
            raise ValueError("NASA_unit_mismatch")
        series = values[key]
        if set(series) != expected:
            raise ValueError("incomplete_or_wrong_climate_period")
        monthly = defaultdict(list)
        for text in sorted(series):
            value = series[text]
            if value is None or isinstance(value, bool):
                raise ValueError("NASA_missing_value")
            v = float(value)
            low, high = (-100, 70) if key == "T2M" else (0, 3000)
            if not np.isfinite(v) or v == payload["header"].get("fill_value", -999) or not low <= v <= high:
                raise ValueError("NASA_missing_or_invalid_value")
            monthly[text[:6]].append(v)
        for text, vals in monthly.items():
            year, month = int(text[:4]), int(text[4:])
            if len(vals) != monthrange(year, month)[1]:
                raise ValueError("incomplete_month")
            by_month[(key, month)].append(float(np.mean(vals) if key == "T2M" else np.sum(vals)))
        for month in range(1, 13):
            vals = by_month[(key, month)]
            if len(vals) != 20:
                raise ValueError("incomplete_climate_years")
            result[f"{'tmean' if key == 'T2M' else 'rain'}_m{month:02}"] = float(np.mean(vals))
    return result


def acquire_power(lat, lon, root):
    coordinates(lat, lon)
    params = {"parameters": "T2M,PRECTOTCORR", "community": "AG",
              "latitude": lat, "longitude": lon, "start": "20010101", "end": "20201231",
              "format": "JSON", "time-standard": "UTC"}
    url = POWER_URL + "?" + urlencode(params)
    path = Path(root) / ("power-" + digest(params)[:24] + ".json")
    evidence = download(url, path, max_bytes=6_000_000)
    payload = read_json(path)
    returned = payload["geometry"]["coordinates"]
    if abs(returned[0]-lon) > .001 or abs(returned[1]-lat) > .001:
        raise ValueError("NASA_returned_point_mismatch")
    return power_features(payload), {
        **evidence, "path": str(path), "source": "NASA POWER", "header": payload["header"],
        "returned_geometry": payload["geometry"], "period": PERIOD,
        "point": [lon, lat], "resolution_notice": "Native coarse meteorological grid, not a farm sensor",
    }


def soil_mean(path, bounds):
    """Area-weighted mean over all output pixel centers; reject >5% masked area.

    WCS geographic subsets are nearest-neighbor reprojections of the native
    ~250 m predictions, not finer soil evidence. Never fill masked pixels.
    """
    west, south, east, north = bounds
    with rasterio.open(path) as src:
        if src.crs != rasterio.crs.CRS.from_epsg(4326) or src.count != 1 or src.nodata is None:
            raise ValueError("Soil_subset_CRS_or_mask_missing")
        if not np.allclose(tuple(src.bounds), bounds, atol=.0001):
            raise ValueError("Soil_subset_extent_mismatch")
        if not (.001 <= abs(src.res[0]) <= .02 and .001 <= abs(src.res[1]) <= .02):
            raise ValueError("Unexpected_soil_subset_resolution")
        data = src.read(1, masked=True)
        if not np.isfinite(data.compressed()).all():
            raise ValueError("Soil_nonfinite")
        lats = np.array([src.xy(r, 0)[1] for r in range(src.height)])
        weights = np.broadcast_to(np.cos(np.radians(lats))[:, None], data.shape)
        valid = ~np.ma.getmaskarray(data)
        fraction = float(weights[valid].sum() / weights.sum())
        if fraction < .95:
            raise ValueError(f"Soil_insufficient_valid_area:{fraction:.3f}")
        value = float(np.average(data.data[valid], weights=weights[valid])) / 10
        return value, {"valid_area_fraction": fraction, "crs": str(src.crs),
                       "bounds": list(src.bounds), "resolution": list(src.res),
                       "nodata": src.nodata, "depth_cm": [0, 5], "statistic": "mean",
                       "conversion_divisor": 10, "aggregation": "cos(latitude)-weighted pixel mean"}


def acquire_soil_wcs(lat, lon, root):
    # Label grid is verified at 5 arc minutes; these are its center coordinates.
    coordinates(lat, lon)
    half = 1/24
    bounds = [lon-half, lat-half, lon+half, lat+half]
    output, sources = {}, {}
    for prop, feature in SOIL_PROPERTIES.items():
        params = [("map", f"/map/{prop}.map"), ("SERVICE", "WCS"), ("VERSION", "2.0.1"),
                  ("REQUEST", "GetCoverage"), ("COVERAGEID", f"{prop}_0-5cm_mean"),
                  ("FORMAT", "GEOTIFF_INT16"),
                  ("SUBSET", f"X({bounds[0]},{bounds[2]})"),
                  ("SUBSET", f"Y({bounds[1]},{bounds[3]})"),
                  ("SUBSETTINGCRS", "http://www.opengis.net/def/crs/EPSG/0/4326"),
                  ("OUTPUTCRS", "http://www.opengis.net/def/crs/EPSG/0/4326")]
        url = SOIL_URL + "?" + urlencode(params)
        path = Path(root) / ("soil-" + digest(params)[:24] + ".tif")
        evidence = download(url, path, max_bytes=1_000_000)
        value, details = soil_mean(path, bounds)
        output[feature] = value
        sources[prop] = {**evidence, **details, "path": str(path),
                         "source": "ISRIC SoilGrids", "product": f"{prop}_0-5cm_mean"}
    return output, sources


def native_soil_mean(vrt_path, lat, lon, root):
    """Subset documented native tiles, preserving explicit -32768 masks.

    A densified label-cell polygon is transformed with always_xy and matched to
    native 250 m pixel centers. Equal-area native pixels receive equal weights.
    """
    import xml.etree.ElementTree as ET
    from urllib.parse import urljoin
    from affine import Affine
    from pyproj import CRS, Transformer
    from rasterio.features import geometry_mask
    from rasterio.merge import merge
    from rasterio.windows import from_bounds

    doc = ET.parse(vrt_path).getroot()
    nodata = float(doc.findtext("./VRTRasterBand/NoDataValue"))
    if nodata != -32768:
        raise ValueError("Unverified_native_soil_NoData")
    crs = CRS.from_wkt(doc.findtext("SRS"))
    coefficients = [float(x) for x in doc.findtext("GeoTransform").split(",")]
    transform = Affine.from_gdal(*coefficients)
    if transform.a != 250 or transform.e != -250:
        raise ValueError("Unexpected_native_soil_resolution")
    half = 1/24
    west, south, east, north = lon-half, lat-half, lon+half, lat+half
    edge = np.linspace(0, 1, 17)
    ring = ([(west+(east-west)*v, south) for v in edge] +
            [(east, south+(north-south)*v) for v in edge] +
            [(east-(east-west)*v, north) for v in edge] +
            [(west, north-(north-south)*v) for v in edge] + [(west, south)])
    transformer = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
    projected = [transformer.transform(x, y) for x, y in ring]
    if not np.isfinite(projected).all():
        raise ValueError("Soil_coordinate_transform_failed")
    xs, ys = zip(*projected)
    bounds = [min(xs), min(ys), max(xs), max(ys)]
    # Discontinuous projection lobes must not trigger an enormous subset.
    if bounds[2]-bounds[0] > 50000 or bounds[3]-bounds[1] > 50000:
        raise ValueError("Soil_projection_seam_requires_manual_subset")
    window = from_bounds(*bounds, transform=transform)
    source_url = read_json(Path(vrt_path).with_suffix(".vrt.source.json"))["url"]
    tiles = []
    for source in doc.findall("./VRTRasterBand/ComplexSource"):
        dst = source.find("DstRect")
        x, y, width, height = (float(dst.attrib[k]) for k in ("xOff", "yOff", "xSize", "ySize"))
        if (x+width <= window.col_off or x >= window.col_off+window.width or
                y+height <= window.row_off or y >= window.row_off+window.height):
            continue
        relative = source.findtext("SourceFilename")
        url = urljoin(source_url, relative)
        path = Path(root) / ("tile-" + digest(url)[:24] + ".tif")
        evidence = download(url, path, max_bytes=10_000_000)
        tiles.append({**evidence, "path": str(path)})
    if not tiles:
        raise ValueError("Soil_no_intersecting_tiles")
    handles = []
    try:
        for tile in tiles:
            src = rasterio.open(tile["path"])
            handles.append(src)
            if src.nodata != nodata or not CRS.from_wkt(src.crs.to_wkt()).equals(crs):
                raise ValueError("Soil_native_tile_metadata_mismatch")
        data, out_transform = merge(handles, bounds=bounds, nodata=nodata)
        polygon = {"type": "Polygon", "coordinates": [projected]}
        inside = geometry_mask([polygon], out_shape=data.shape[1:], transform=out_transform, invert=True)
        if not inside.any():
            raise ValueError("Soil_empty_polygon")
        valid = inside & (data[0] != nodata)
        fraction = float(valid.sum()/inside.sum())
        if fraction < .95:
            raise ValueError(f"Soil_insufficient_valid_area:{fraction:.3f}")
        # Validate native integer values before averaging, not just the mean.
        upper = 140 if Path(vrt_path).name.startswith("phh2o_") else 10000 if Path(vrt_path).name.startswith("soc_") else 1000
        if np.any((data[0][valid] < 0) | (data[0][valid] > upper)):
            raise ValueError("Soil_native_value_out_of_documented_units")
        value = float(data[0][valid].mean())/10
        return value, {"path": str(vrt_path), "vrt_sha256": sha256_local(vrt_path),
                       "tiles": tiles, "source": "ISRIC SoilGrids", "access": "WebDAV_native",
                       "period": "static modeled soil product, not annual observations",
                       "depth_cm": [0, 5], "statistic": "mean", "nodata": nodata,
                       "crs": crs.to_wkt(), "resolution_m": [250, 250],
                       "valid_area_fraction": fraction, "conversion_divisor": 10,
                       "bounds_wgs84": [west, south, east, north],
                       "aggregation": "native equal-area pixel centers inside densified GAEZ polygon"}
    finally:
        for src in handles:
            src.close()


def sha256_local(path):
    from .common import sha256
    return sha256(path)


def acquire_soil(lat, lon, root):
    coordinates(lat, lon)
    output, sources = {}, {}
    for prop, feature in SOIL_PROPERTIES.items():
        name = f"{prop}_0-5cm_mean.vrt"
        url = f"https://files.isric.org/soilgrids/latest/data/{prop}/{name}"
        path = Path(root) / name
        download(url, path, max_bytes=10_000_000)
        output[feature], sources[prop] = native_soil_mean(path, lat, lon, root)
        sources[prop]["product"] = f"{prop}_0-5cm_mean"
    return output, sources
