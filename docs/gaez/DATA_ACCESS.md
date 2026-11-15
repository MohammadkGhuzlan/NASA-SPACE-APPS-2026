# GAEZ evidence engine — source-access verification

Verified **2026-11-15**, before agricultural UI integration.

## Result

**Genuine GAEZ v5 categorical suitability rasters were acquired, interpreted and
sampled successfully.** The selected variable is **RES05-SIX**, not the
continuous RES05-SXX variable used by the separate Phase 4 research pipeline.

The official sources verified were:

- [FAO GAEZ](https://www.fao.org/gaez/en)
- [Official platform guide](https://github.com/un-fao/gaezv5/wiki/21.-GAEZ-v5-Platform-User-Guide)
- [Official selective-download notebook](https://github.com/un-fao/gaezv5/blob/main/GAEZ-v5-Platform/Data-Access-Notebooks/gaez_res05_downloader_selection_notebook.ipynb)
- [RES05 catalog workbook](https://data.apps.fao.org/catalog/dataset/514c92d5-9e01-4c70-814a-80ea1ca9fe6a/resource/768b08ad-be9c-427a-84be-3a3d6dd7835a/download/_readme_res05.xlsx)
- [Dataset metadata API](https://data.apps.fao.org/catalog/api/3/action/package_show?id=514c92d5-9e01-4c70-814a-80ea1ca9fe6a)
- [Dataset dimensions](https://data.apps.fao.org/catalog/dataset/514c92d5-9e01-4c70-814a-80ea1ca9fe6a/resource/e69258af-55e4-49e3-a749-3e5a38c49244/download/res05.json)
- [Official categorical style/definitions](https://data.apps.fao.org/gismgr/api/v2/catalog/workspaces/GAEZ-V5/styles/SIX/sld)

The notebook explicitly documents resolving the workbook's `LIST_FILES` rows
into public Google Cloud Storage objects. This implementation uses that
documented path, not guessed filenames or screenshot-derived pixel colors.
The workbook's crop, variable, climate, period and management dimensions are
checked before selecting files.

## Authentic initial proof

Exact object:

```text
https://storage.googleapis.com/fao-gismgr-gaez-v5-data/DATA/GAEZ-V5/MAPSET/RES05-SIX/GAEZ-V5.RES05-SIX.HP0120.AGERA5.HIST.WHE.LRLM.tif
```

| Field | Verified value |
|---|---|
| Product/framework | FAO / IIASA GAEZ v5 |
| Dataset | Crop suitability, class index (Global – 20 years average – ~10 km) |
| Variable | RES05-SIX; all land in grid cell |
| Crop | WHE — Wheat |
| Management | LRLM — Rain-fed and low input level of management |
| Period | HP0120 — 2001–2020 |
| Climate source / scenario | AGERA5 / HIST |
| CRS | EPSG:4326 |
| Grid | 4,320 columns × 2,160 rows |
| Bounds | −180…180 longitude; −90…90 latitude, with masked/unassessed cells |
| Resolution | 1/12 degree = 5 arc minutes; approximately 10 km at equator |
| Format/type | Single-band tiled LZW GeoTIFF, UInt8 |
| NoData | 0, verified in GeoTIFF header and official style |
| Units | Categorical class identifiers, not a percentage |
| Original bytes | 583,419 |
| SHA-256 | `90d7ca4613c791582cdd31ec9306e86706c3b70a17034de1e91dbdae334d4ce5` |
| First recorded acquisition | 2026-11-15T13:25:12.989439+00:00 |
| Córdoba extraction | 37.8882, −4.7794 → **6, SI >10 : Marginal** |

The numerical **6** is a class identifier. It does not mean 6% suitable,
6% success probability or an expected yield.

## Exact class definitions

Verified against the official SLD, with no inferred breaks:

| Code | Official label |
|---:|---|
| 0 | no data |
| 1 | SI >85 : Very high |
| 2 | SI >70 : High |
| 3 | SI >55 : Good |
| 4 | SI >40 : Medium |
| 5 | SI >25 : Moderate |
| 6 | SI >10 : Marginal |
| 7 | SI >0 : Very marginal |
| 8 | Not suitable |
| 9 | Water |

The thresholds in the published labels describe FAO's suitability-index
classification. They are not harvest-success probabilities. Water and NoData
are not successful agricultural assessments. This engine does not convert
classes back into a fabricated continuous index, mix them with SXX's
0–10,000 scale/−9 NoData, or rank different crops numerically.

## Verified crop and scenario subset

| Code | Official crop |
|---|---|
| WHE | Wheat |
| BRL | Barley |
| MZE | Maize |
| SOY | Soybean |
| CHK | Chickpea |
| RCD | Dryland rice |
| RCW | Wetland rice |

Generic farmer-entered Rice is ambiguous: the UI requires an explicit rice
type; the report shows both codes with a warning. The separate catalog crop
GRM is not silently mapped through the existing planner's ambiguous Gram alias.
Other crops remain unsupported **in the acquired subset**, not proven absent
from GAEZ or unsuitable.

| Code | Official scenario |
|---|---|
| HILM | Irrigation and high input level of management |
| HRLM | Rain-fed and high input level of management |
| LILM | Irrigation and low input level of management |
| LRLM | Rain-fed and low input level of management |

Only HP0120 / AGERA5 / HIST is enabled. The workbook describes other historical
and future periods, but they were not acquired or activated; no weather forecast
is supplied.

## Actual acquired assets

**28 complete selected GeoTIFFs, 15,668,630 bytes total.** This is a small
crop/scenario subset, not the full global collection. The 4,046,932-byte official
workbook is an inventory, not a bulk raster download.

All objects below were resolved from actual official workbook rows. Their
common exact URL prefix is:

```text
https://storage.googleapis.com/fao-gismgr-gaez-v5-data/DATA/GAEZ-V5/MAPSET/RES05-SIX/
```

```text
GAEZ-V5.RES05-SIX.HP0120.AGERA5.HIST.BRL.HILM.tif
GAEZ-V5.RES05-SIX.HP0120.AGERA5.HIST.BRL.HRLM.tif
GAEZ-V5.RES05-SIX.HP0120.AGERA5.HIST.BRL.LILM.tif
GAEZ-V5.RES05-SIX.HP0120.AGERA5.HIST.BRL.LRLM.tif
GAEZ-V5.RES05-SIX.HP0120.AGERA5.HIST.CHK.HILM.tif
GAEZ-V5.RES05-SIX.HP0120.AGERA5.HIST.CHK.HRLM.tif
GAEZ-V5.RES05-SIX.HP0120.AGERA5.HIST.CHK.LILM.tif
GAEZ-V5.RES05-SIX.HP0120.AGERA5.HIST.CHK.LRLM.tif
GAEZ-V5.RES05-SIX.HP0120.AGERA5.HIST.MZE.HILM.tif
GAEZ-V5.RES05-SIX.HP0120.AGERA5.HIST.MZE.HRLM.tif
GAEZ-V5.RES05-SIX.HP0120.AGERA5.HIST.MZE.LILM.tif
GAEZ-V5.RES05-SIX.HP0120.AGERA5.HIST.MZE.LRLM.tif
GAEZ-V5.RES05-SIX.HP0120.AGERA5.HIST.RCD.HILM.tif
GAEZ-V5.RES05-SIX.HP0120.AGERA5.HIST.RCD.HRLM.tif
GAEZ-V5.RES05-SIX.HP0120.AGERA5.HIST.RCD.LILM.tif
GAEZ-V5.RES05-SIX.HP0120.AGERA5.HIST.RCD.LRLM.tif
GAEZ-V5.RES05-SIX.HP0120.AGERA5.HIST.RCW.HILM.tif
GAEZ-V5.RES05-SIX.HP0120.AGERA5.HIST.RCW.HRLM.tif
GAEZ-V5.RES05-SIX.HP0120.AGERA5.HIST.RCW.LILM.tif
GAEZ-V5.RES05-SIX.HP0120.AGERA5.HIST.RCW.LRLM.tif
GAEZ-V5.RES05-SIX.HP0120.AGERA5.HIST.SOY.HILM.tif
GAEZ-V5.RES05-SIX.HP0120.AGERA5.HIST.SOY.HRLM.tif
GAEZ-V5.RES05-SIX.HP0120.AGERA5.HIST.SOY.LILM.tif
GAEZ-V5.RES05-SIX.HP0120.AGERA5.HIST.SOY.LRLM.tif
GAEZ-V5.RES05-SIX.HP0120.AGERA5.HIST.WHE.HILM.tif
GAEZ-V5.RES05-SIX.HP0120.AGERA5.HIST.WHE.HRLM.tif
GAEZ-V5.RES05-SIX.HP0120.AGERA5.HIST.WHE.LILM.tif
GAEZ-V5.RES05-SIX.HP0120.AGERA5.HIST.WHE.LRLM.tif
```

Each acquisition records its exact URL, source row, byte count, timestamp,
ETag, SHA-256 and inspected header in the local manifest and sidecars.
Per-lookup provenance and the saved report retain the asset identifier/hash.

## Access methods and reuse

- Official metadata/catalog APIs returned usable JSON/workbook data.
- Public Google Cloud Storage object GETs returned actual TIFFs, without a
  service account or API key.
- A byte-range probe returned **206**, `bytes 0-15/583419`, with 16 bytes.
  Remote range access is possible, but this implementation deliberately uses
  complete, checksum-verified small selected rasters for reproducibility.
- No undocumented FAO numerical point-query endpoint is assumed. WMTS map
  images are not treated as numerical suitability evidence.
- Source acquisition is an explicit operator CLI, never triggered by farm
  lookup requests. It has a single-ingestor lock, per-file locks, bounded
  retries/timeouts, resumable partial files, a 5 MB per-raster limit and a
  40 MB selected-raster budget. Public lookups read locally.
- GeoTIFF binaries and raw source caches are ignored by Git and deployment
  packaging. They can be reacquired using the documented CLI; no raster
  binaries are stored in PostgreSQL.

## License and attribution

The dataset's own metadata declares **CC BY 4.0**. The notebook explicitly
supports programmatic selective downloads. Reuse must retain attribution,
source links, license and a statement of changes:

> FAO and IIASA (2025), GAEZ v5. Class-raster point extraction by Field Shift;
> no endorsement.

Field Shift extracts a containing cell and formats its original class code;
it does not alter the suitability raster or claim a current farm observation.

## Reproduce

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=artifacts/api-server \
  uv run --no-sync python -B -m backend.gaez.ingest
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=artifacts/api-server \
  uv run --no-sync python -B -m unittest discover \
  -s artifacts/api-server/tests -p test_gaez.py -v
```

The live-source tests require actual acquisition: absence is a failure, not an
automatic mock or skip. They compare service window reads against separate
`rasterio.sample` extraction at **140** site/crop/scenario combinations and
also locate an actual NoData pixel in the source raster. Both extraction paths
use GDAL/Rasterio; this is reproducibility checking, not independent agronomic
validation of FAO's underlying assessment.
