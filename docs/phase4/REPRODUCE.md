# Phase 4: isolated, file-only research

**Do not activate a model, change the planner, run migrations, or deploy this work.**
The target is an approximation of FAO/IIASA GAEZ v5 modeled suitability, not
observed yield, crop success, profit, water savings or rotation benefits.
Read `REPORT.md` and `MODEL_CARD.md` for the actual run outcome.

## Runtime

Python 3.12, `uv sync --locked` from the repository root. The repository lock
records NumPy, pandas, scikit-learn, SciPy, joblib, rasterio, pyproj and openpyxl.
Nix `expat` is required by rasterio's GDAL wheel in this environment; it is
recorded in `.replit`. Existing PROJ remains configured.
No database connection, web server, secret, frontend, or cloud account is
required by this package.

```sh
export PYTHONPATH=artifacts/api-server
ML="uv run python -m backend.machine_learning"
RUN=generated-artifacts/phase4
```

`generated-artifacts/` is excluded from Git and deployments. It is a local
working cache, **not a durable shared dataset repository**. Copy it to approved
durable research storage separately before discarding this task workspace.
Never put raw rasters or pickles in ordinary Git history.

## 1. Official source discovery and labels

```sh
$ML labels --root "$RUN/labels"
$ML sample --root "$RUN/labels" --cells 180 --seed 42 --out "$RUN/samples.json"
$ML audit --run-root "$RUN" --out docs/phase4/evidence
```

`labels` downloads the official RES05 Excel catalog and CKAN metadata, checks
dimension meanings, selects exact catalog rows, downloads all five ~10 km
GeoTIFFs, validates CRS/grid/range/NoData, and saves a manifest and SHA-256
sidecars. The downloaded catalog, not an invented filename pattern, controls
layer selection. It uses:

* `RES05-SXX`, **not** suitability classes, yields, or the separate ~1 km product;
* `HP0120` = 2001–2020, `AGERA5`, `HIST`;
* `LRLM` = rain-fed and low input management;
* `WHE`, `BRL`, `MZE`, `RCD`, `RCW`.

Generic “rice” is deliberately unsupported: dryland and wetland rice are
different catalog crop types. Other crop, management, reference-period and
resolution combinations require separate metadata review and a new contract.

Sampling draws from cells valid in **all five layers**, retaining true zeros.
It screens to latitude −60…75, takes a seeded bounded candidate pool,
round-robins 20° geographic strata, and keeps at most one candidate per
1.5° screening bin. It does not balance on suitability values or assume all
sampled cells are cropland. This is a diverse **pilot**, not an area-weighted
global benchmark or verified climate-zone stratification. Count rows and
source cells separately. Changing the sample size can change the sample.

## 2. Environmental acquisition and preparation

```sh
$ML prepare --samples "$RUN/samples.json" \
  --cache "$RUN/environment" --out "$RUN/prepared"
```

The default runs two cell workers. Each HTTP operation has at most three
attempts, bounded delays, an explicit size budget and timeout, and a 0.5-second
post-download pause. Avoid running concurrent preparation batches against the
same providers. Downloads are atomic and hash checked; range resumption uses
ETag/If-Range. Restarting the same command reuses intact downloads.
The incremental `progress.json` records exclusions after each processed cell.
An interrupted run is **not** a completed dataset. Restart rather than treating
the incremental report as training input.

### NASA POWER

* Independent historical client requests `T2M` and `PRECTOTCORR`, AG community,
  UTC, January 1, 2001–December 31, 2020, at each label-cell center.
* Every expected daily value must be present, have matching units, and pass
  physical screening. No interpolation or missing-value imputation.
* Features are 12 calendar-month temperature means and 12 calendar-month mean
  precipitation totals. Monthly statistics are first computed per year, then
  each of the 20 years receives equal weight.
* No seasonal planting calendar, reference evapotranspiration, heat damage,
  POWER wetness, or SMAP feature is inferred.
* Returned point geometry is not proof of a unique native weather grid cell.
  Split purging conservatively rejects potentially shared coarse footprints
  rather than treating small coordinate differences as independent evidence.

### SoilGrids

The automatic path uses official WebDAV native 250 m mean layers for
clay, sand, silt, pH in water and organic carbon, all at **0–5 cm**.
It downloads small intersecting native tiles listed in each official VRT.
It transforms a densified GAEZ-cell boundary into the native interrupted
Goode Homolosine projection with explicit longitude/latitude ordering.
Only native pixel centers inside the polygon contribute; equal-area pixels
are equally weighted. This is a pixel-center area approximation, not exact
fractional overlap at boundary pixels.

Native `-32768` masks are retained; at least 95% of polygon pixels must be
valid for **every** property. Source units are checked through physical
screening and divided by 10: texture g/kg → %, pH×10 → pH,
SOC dg/kg → g/kg. Texture totals must be within one percentage point of 100.
No nearest town, farmer assertion, or `PROXY_DEMO_ONLY` record is substituted.
Projection seams requiring an unusually large subset are rejected explicitly.
Static SoilGrids estimates are not observations from every climate-reference year.

WCS acquisition/parsing is available separately as `acquire_soil_wcs`, but is
not the default: inspected WCS responses omitted NoData metadata. This path
rejects those files instead of guessing that zero is missing.

## 3. Review quality before training

Inspect:

* `prepared/quality.json`: exclusions, missingness, crop and label distributions,
  extent, geographic strata, label-cell and conservative environmental counts;
* `prepared/dataset.json`: original evidence paths/hashes per feature group;
* `labels/manifest.json`: source metadata, selected rows and raster identities.

The four original historical CSVs remain unchanged. Their 2019–2025 NASA
period and proxy soil provenance do not satisfy this contract.

## 4. Training and final holdout

```sh
$ML train --dataset "$RUN/prepared/dataset.json" --out "$RUN/training"
```

Training replays the labels and environmental features from hash-verified
original source files. There is no generic “trust this CSV” shortcut.
The checked-in `config.json` declares the gates **before** final-test inspection.
Default readiness: 120 source cells overall; train/validation/test minimum
60/20/20 cells; six 10° blocks per partition; all five crops; at least a
3,000-point label span in training and validation for each crop.

Geographic blocks are assigned by seeded SHA-256 (approximately 60/20/20).
All crops from one cell stay together. Test geography has priority, then
validation, then train. Across partitions, remove cells within 150 km or
within a conservative shared meteorological footprint envelope, including
antimeridian handling. Three training-only GroupKFold folds are buffered in
the same way. Coordinates and block IDs never enter model features.

Dummy mean and per-crop mean baselines are compared to Ridge (alpha 1, 10)
and Random Forest (150 trees; minimum leaf 3, 8). Preprocessing is fitted
separately inside training folds, then on training only. Validation MAE
selects the candidate; it is not refitted on validation or test.
Predictions are clipped to the **verified target range**, not interpreted
as probabilities. Test is evaluated only after the validation gate passes.

Default acceptance requires:

* aggregate MAE ≤1,500 index points and R² ≥0.2;
* ≥10% MAE improvement over **both** dummy and per-crop mean baselines;
* each crop ≥20 final-test source cells, MAE ≤1,800, no worse than crop mean;
* every reported geographic region ≥5 final-test source cells and MAE ≤2,000.

These are conservative project screening criteria, **not FAO-endorsed accuracy
standards**. Sparse regional evidence rejects promotion instead of being hidden.
Geographic regions are diagnostic latitude/longitude bins, not verified
agroclimatic zones.

The dataset's sibling `.holdout/<dataset-hash>.json` is exclusively reserved
before final evaluation. A second output directory does not allow the same
dataset to be selected against the final test again. Do not remove this ledger
or alter thresholds after seeing test results. For reproduction, compare saved
evidence; a genuinely independent assessment requires preregistered new
geography. A crash after reservation requires an audited recovery decision,
not automatic reuse.

If rejected or insufficient, the command exits 2 and **does not save an
estimator**. Metrics/evidence and readiness reports remain available.
Only accepted runs create `accepted.joblib` and `evaluation.json` with fitted
preprocessing, source and dataset hashes, library versions, splits, config,
support diagnostics and evaluation.

After the run finishes, capture small reviewable evidence without copying
rasters or repeating the holdout:

```sh
$ML evidence --run-root "$RUN" --out docs/phase4/evidence
```

This reuses the saved evaluation/readiness result, verifies the dataset
identity, and records actual counts, reasons and an actual availability
response. Do not regenerate the checked-in audit/evidence while running
software tests with synthetic inputs.

### Preregistered supplement after the initial readiness failure

The initial 180-cell pilot retained only 95 eligible cells and 11 test cells.
The gates were not changed. The additional target-independent geographic
protocol, including fixed 60/40/20 test/train/validation quotas, is recorded
in [`SUPPLEMENT_PROTOCOL.md`](SUPPLEMENT_PROTOCOL.md).

```sh
$ML supplement --samples "$RUN/samples.json" --out "$RUN/supplemented-samples.json"
$ML prepare --samples "$RUN/supplemented-samples.json" \
  --cache "$RUN/environment" --out "$RUN/supplemented"
$ML train --dataset "$RUN/supplemented/dataset.json" --out "$RUN/supplemented-training"
$ML evidence --run-root "$RUN" --prepared-name supplemented \
  --training-name supplemented-training --out docs/phase4/evidence
```

The supplement retains all original cells/exclusions and adds 120 new spaced
cells, producing a 300-cell planned sample. It deliberately oversamples test
geography to address sample support, not test performance. It does not create
an area-weighted worldwide benchmark. The source audit's 180-cell count
describes the initial pilot; the final quality/evaluation evidence describes
the combined run.

## Manual import if official access stops working

Use exact URLs in `evidence/source-audit.json` for these files:

```
catalog.xlsx
metadata.json
GAEZ-V5.RES05-SXX.HP0120.AGERA5.HIST.BRL.LRLM.tif
GAEZ-V5.RES05-SXX.HP0120.AGERA5.HIST.MZE.LRLM.tif
GAEZ-V5.RES05-SXX.HP0120.AGERA5.HIST.RCD.LRLM.tif
GAEZ-V5.RES05-SXX.HP0120.AGERA5.HIST.RCW.LRLM.tif
GAEZ-V5.RES05-SXX.HP0120.AGERA5.HIST.WHE.LRLM.tif
```

Place them in a new label directory, preserving bytes. Beside **each** file
create `<filename>.source.json` containing `url`, `sha256`, `bytes`,
`retrieved_at` (ISO UTC) and `etag` (null if unavailable). SHA-256 must match
the saved bytes. An operator must verify that these really came from FAO;
checksums alone do not establish authenticity. Existing audit hashes allow
comparison to this run.

```sh
$ML import-labels --root generated-artifacts/manual-labels
```

This runs the same catalog, metadata, raster, and provenance checks. No
unidentified raster/CSV, different crop equivalent, or guessed scale is accepted.
For environmental outages, retain the explicit missing-source exclusions;
restore official access or supply the exact cached response/tile bytes and
their matching original acquisition sidecars. Never hand-fill feature means.

## Offline tests

```sh
PYTHONPATH=artifacts/api-server uv run python -m unittest discover \
  -s artifacts/api-server/tests -p test_machine_learning.py -v
PYTHONPATH=artifacts/api-server uv run python -m unittest discover \
  -s artifacts/api-server/tests -v
pnpm run typecheck
```

The full existing regression suite additionally requires the configured
**development** database and its existing seeded schema. Tests use rolled-back
transactions; do not run migrations or point them at production.
Test-only synthetic calendars, labels and temporary estimators are clearly
separated from scientific data and never bundled as genuine trained models.
