# Source/access audit and interpretation

Checked November 15, 2026. Machine-readable identities, retrieval times and
SHA-256 hashes are in `evidence/source-audit.json`. The original files and
planner were inspected, not replaced.

## Existing four-location inputs

| File | Original records | Meaning | Scientific training eligibility |
|---|---:|---|---|
| `nasa_daily.csv` | 10,228 | Five climate parameters, 2019–2025 | No suitability labels; wrong period |
| `nasa_monthly.csv` | 336 | Derived monthly summaries | Not independent observations or labels |
| `nasa_soil_moisture_daily.csv` | 10,228 | POWER modeled wetness fractions | Not SMAP; wrong period; not labels |
| `soilgrids_0_5cm_aligned.csv` | 4 | Nearby modeled soil proxies | `PROXY_DEMO_ONLY`, not field measurements |

All four exist and match the corresponding original archive members byte for
byte. Sites are Irbid, Al Ain, Colusa and Stuttgart, as specified in the brief.
The soil offset discrepancy already documented for Al Ain remains unchanged.
The CSV climate file does not embed complete original acquisition metadata.
None is promoted to independent training truth.

## FAO / IIASA GAEZ v5

* Publisher: FAO Land and Water Division; originator: IIASA.
* Official repository:
  <https://github.com/un-fao/gaezv5>
* Inspected repository revision:
  `6c712bf83d46002e7718240a53fe2404d56f5bc7`.
* Downloader:
  `GAEZ-v5-Platform/Data-Access-Notebooks/gaez_res05_downloader_selection_notebook.ipynb`.
* Catalog URL: recorded verbatim in `labels.py` and the source audit.
* Selected metadata:
  <https://data.apps.fao.org/catalog/dataset/41a4b84d-61a4-4f53-af44-2eb80b9c6237>
* Machine-readable package:
  <https://data.apps.fao.org/catalog/api/3/action/package_show?id=d666d360-0e3c-467c-beb0-29ad55df5855>

Title: **Crop suitability, continuous index (Global – 20 years average –
~10 km) – GAEZ v5**. Catalog metadata edition says “Version 2.0”; the model
framework/product is GAEZ **v5**, not GAEZ v2. Publication March 24, 2025.

`RES05-SXX`: index 0–10,000, scale factor 1, NoData −9, Int16,
EPSG:4326, 4320×2160, 0.0833333333° (5 arc minutes), bounds
−180…180/−90…90. GeoTIFF headers and all unmasked values were checked.
This is the **all-land** index, not the best observed yield or a class.
The separate `SXX30AS` product is ~1 km and was inspected in metadata but not
substituted or mixed into this dataset.

Confirmed dimensions:

| Dimension | Code | Official interpretation |
|---|---|---|
| Climate period | HP0120 | 2001–2020 |
| Climate source | AGERA5 | AgERA5 |
| Climate scenario | HIST | Historical |
| Water/management | LRLM | Rain-fed and low input level of management |
| Crop | WHE | Wheat |
| Crop | BRL | Barley |
| Crop | MZE | Maize |
| Crop | RCD | Dryland rice |
| Crop | RCW | Wetland rice |

All five exact catalog-resolved GeoTIFF downloads returned HTTP 200 and were
retrieved. Each contains **3,259,820 valid label cells**; the repeated crop
layers do not imply five independent environmental samples per cell.
The deterministic pilot sampled 180 valid cells / 900 labels.
The preregistered geographic supplement added 120 source cells / 600 labels,
for a combined 300-cell planned sample. See `SUPPLEMENT_PROTOCOL.md` and
`evidence/supplement-sampling.json`; source rasters and label semantics did
not change. The combined environmental alignment retained 124 cells.

Reuse: **CC BY 4.0**. Attribute “FAO and IIASA (2025), GAEZ v5 suitability
index”; note Field Shift's subsetting, aggregation and approximation.
This model-derived assessment does not verify actual crop production or the
benefits of a management choice.

## NASA POWER

* API and historical time-standard documentation:
  <https://power.larc.nasa.gov/docs/services/api/temporal/daily/>
* Source methodology:
  <https://power.larc.nasa.gov/docs/methodology/>
* Acknowledgement/use guidance:
  <https://power.larc.nasa.gov/docs/faqs/data/>
* Endpoint: <https://power.larc.nasa.gov/api/temporal/daily/point>

Requests use the AG community, UTC and a complete 2001–2020 interval.
`T2M` is C and `PRECTOTCORR` mm/day. Original response headers, returned point,
URL, units, bytes, retrieval time and hash are retained. POWER's historical
meteorological sources are gridded modeled/reanalysis products; documented
meteorological resolution is approximately 0.5° latitude × 0.625° longitude,
not 250 m or field-scale weather. Requested/returned coordinates are **not**
treated as a native weather-cell ID.

POWER is openly accessible; retain NASA POWER acknowledgement and consult its
official data-use guidance when redistributing. No NASA logo or endorsement
is implied. A separate SPDX-style license identifier for the API responses was
not established in this audit; do not invent one or apply GAEZ/SoilGrids'
CC BY license to NASA data. The raw cache is not redistributed in Git.

Same reference years do not make NASA POWER and the AgERA5 climate used by
GAEZ identical. The pipeline measures approximation error, not equivalence
of the climate products.

## ISRIC SoilGrids

* Product, CC BY 4.0 license and REST service warning:
  <https://isric.org/explore/soilgrids>
* Units, depth, masks and uncertainty:
  <https://docs.isric.org/globaldata/soilgrids/SoilGrids_faqs_01.html>
* WCS:
  <https://docs.isric.org/globaldata/soilgrids/wcs.html>
* WebDAV:
  <https://docs.isric.org/globaldata/soilgrids/WebDav.html>
* Native VRT/tile tree:
  <https://files.isric.org/soilgrids/latest/data/>

The provider reports REST service issues/temporary suspension. Two actual
REST probes in this task returned HTTP 200 but null means. This is not evidence
of usable soil data. WCS capabilities and subsets were accessible; the inspected
Int16 subsets had `nodata=None` and empty `nilValues` in DescribeCoverage.
They were rejected, not assigned an invented missing-value interpretation.

Native WebDAV VRTs explicitly document −32768 missing pixels, 250 m native
resolution and interrupted Goode Homolosine projection. Native tile acquisition
is the implemented alternative. Keep VRT and tile hashes because the `latest`
directory can change. Metadata currently describes the v2.0.0 / 2020 modeled
product; it is static soil estimation, not 2001–2020 repeated soil measurements.

Only mean predictions at 0–5 cm are used. Texture g/kg, pH×10 and SOC dg/kg are
each divided by 10 to %, pH and g/kg. Soil masks and incomplete area coverage
exclude cells; no nearby proxy is used. Attribute **ISRIC – World Soil
Information, SoilGrids** and identify the retrieved product/hash.
Uncertainty quantiles are not included as confidence estimates in this model.

## Unresolved scientific gaps

* More complete soil support and enough independent geography after exclusions.
* An area-weighted global benchmark and verified environmental-zone coverage.
* Root-zone properties, terrain and other GAEZ inputs absent from this compact
  approximation feature set.
* Transfer validation across climate products, regions and management conditions.
* Independent outcomes for any future claim about yield, profit or management
  benefits—GAEZ labels alone cannot supply that evidence.
