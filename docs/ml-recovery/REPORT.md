# Field Shift ML recovery — engineering report A–L

**Recovery completed on 2026-11-15 with no qualified model. Predictions remain
unavailable. This document is not an activation claim.**
The original Phase 4 and Phase 5 reports are preserved unchanged. Recovery
evidence lives beside this report; large source bytes are in ignored
`generated-artifacts/ml-recovery/`, not in Git or a published service.

## A. Root cause: demonstrated findings versus hypotheses

The original supervised experiment genuinely failed geographic validation.
The best candidate, forest leaf 3, achieved MAE **1672.801** index points against
dummy **1717.194**, only **2.585%** improvement; R² **0.0568**. The recorded
rejection was `validation_mae`. Rechecking the saved metrics also demonstrates
failure of the unchanged R² ≥0.2 and ≥10% dummy-improvement screens. These
additional failures were previously hidden by the first-failure return.

An additional, reconstructed **train-only crop-median baseline** achieves
validation MAE **1347.125**. Every crop's training median is zero because of
the authentic zero-heavy all-land target distribution. The old best candidate
is about **24.2% worse** than this MAE-appropriate constant baseline. This is
a software/research diagnostic, not a suggestion to return zero as a farm
prediction. It does not replace or retroactively change the original recorded
rejection reason. The recovery protocol requires improvement over both mean
and median baselines.

There is **no demonstrated preprocessing/unit/crop-code bug explaining these
errors**. Genuine labels were acquired. Reacquisition recovered byte-identical
original RES05-SXX rasters and exactly reconstructed all 300 planned cell
identities, including every previously retained/excluded cell.

Actual independent source-cell counts were 74 train / 24 validation / 26 test,
not 370 / 120 / 130 independent environmental observations. Corresponding
10-degree block counts are **63 / 21 / 21**. Soil completeness excluded
**176/300 cells (58.7%)**: 138 below 95% native valid area, 38 with no intersecting
native tiles. There are 73 occupied 20-degree geographic strata overall, not
73 independently verified agroclimatic regions. Validation had 16 diagnostic
regions, each with just 1–3 cells. Regional support is inadequate for the
original ≥5-cell regional gate; it is not a reason to weaken that gate.

POWER/MERRA2 versus AgERA5 climate-product differences, shallow static soil
features, omitted GAEZ constraints, complete-case selection bias and zero-heavy
all-land labels are **plausible limitations, not proven causes of model error**.
No causal ablation was available in the original evidence. Period alignment
alone does not remove climate-product differences.

Full restoration now reproduces **124 retained cells / 620 rows and exactly
the same 176 exclusion cell identities and reason strings**. All five native
soil VRTs and all **705 distinct native tiles used by retained cells** match
their original byte hashes. This reproduces the observed mask attrition; it
does not establish that excluded areas have unsuitable crops.

The 124 reacquired POWER response byte hashes differ from the old response
hashes. Their scientific request/header contracts match; current responses also
contain request-timing fields. Since the old response bytes are absent, do not
claim byte-for-byte recovery of POWER or invent an explanation for every
difference. The one retained original example's complete 29-feature vector
replays with **maximum absolute difference 0.0**. New response hashes, source
versions and the new dataset identity are retained explicitly.

A real **pooled-model replay on the restored inputs** reproduces all four
original validation MAE/RMSE/R² results to floating-point tolerance
(largest metric delta <5×10⁻¹³). The best forest MAE is exactly the original
1672.8007297084994. This is direct numerical reproduction of the failure, not
merely restating an old report. It gives no evidence of a hidden preprocessing
correction that would justify activating the original model. The replay
correctly reports all visible validation failures and stops before final test.
See [`evidence/pooled-replay-comparison.json`](evidence/pooled-replay-comparison.json)
and [`evidence/pooled-replay-evaluation.json`](evidence/pooled-replay-evaluation.json).

Reproducible diagnostic command:

```sh
PYTHONPATH=artifacts/api-server uv run python -m backend.machine_learning.recovery diagnose
```

See [`evidence/diagnosis.json`](evidence/diagnosis.json) for source hashes,
actual distributions, partition/block counts, every recorded candidate and
reconstructed train-only crop-mean baselines. This diagnosis did not refit the
old candidates or calculate old final-test performance.

## B. Corrections and preservation

* Kept all preexisting FAO integration, routes, UI and generated contracts.
  The initial dirty tracked patch and untracked source archive, base commit
  and database count snapshot were saved under the ignored
  `generated-artifacts/ml-recovery/preservation/` directory before edits.
  Work moved from `gaez-evidence-engine` to isolated `ml-recovery`; no reset,
  deletion, migration, force push or publication.
* Reacquired the correct continuous **RES05-SXX** product. The existing
  **RES05-SIX** lookup cache contains categorical suitability classes and was
  deliberately not substituted for training indices.
* Legacy training now checks all acceptance screens on validation, including
  crop-mean baseline and geographic support, before reserving final test.
  Existing saved Phase 4 evidence was not rewritten.
* Added a cross-dataset, cross-output and cross-split-seed geographic holdout
  reservation. Source product, period, scenario and block determine scientific
  identity, not a newly computed dataset checksum. Reservations are exclusive,
  cross-process locked and retained after crashes. Preserve the shared
  `docs/ml-recovery/holdout-ledger/` ledger with run evidence. Unlike large
  caches, these small scientific reservation records belong in version control.
* Added a separately preregistered per-crop evaluation path. One rejected crop
  cannot reject an independently qualified different crop. A domain must have
  adequate training/validation support before independent testing; unsupported
  regions are explicitly excluded, not promoted on a single held-out point.
* Added an authentic historical farm-input builder using the existing POWER
  and native SoilGrids transforms. It preserves exact selected coordinates and
  separately records the five-arc-minute cell center/soil polygon. It rejects
  unsupported crops/scenarios and missing inputs; no proxy-city substitution.
  Model coverage receives the cell-center coordinate used in training, while
  the exact selected farm coordinate is preserved separately, including at
  geographic block boundaries.
  This builder is research/server-only, not a newly enabled public endpoint.
* Added a bounded acquisition run and independently labeled five-location
  operational checker. Synthetic models/values exist only in software tests.

## C. Dataset, target and sources

Target: approximate **FAO/IIASA GAEZ v5 modeled all-land suitability index**,
RES05-SXX, HP0120, HIST, AgERA5, LRLM (rain-fed and low input), EPSG:4326,
five arc minutes, index 0–10000, scale 1, NoData −9. These are not observed farm
outcomes, classes, yield, profitability, forecast weather or probabilities.
WHE = wheat; BRL = barley; MZE = maize; RCD = dryland rice; RCW = wetland rice.
Generic rice is not silently mapped to a production type.

Features: 12 calendar-month temperature means (`tmean_m01`…`tmean_m12`, °C),
12 mean monthly precipitation totals (`rain_m01`…`rain_m12`, mm/month), clay,
sand and silt (%), pH in water and SOC (g/kg). Crop/scenario are categorical;
coordinates and target never enter model features. Complete daily NASA
POWER/MERRA2 AG **UTC 2001–2020**, equal-weight annual monthly aggregates.
Soil is static ISRIC SoilGrids mean **0–5 cm**, native 250 m masks preserved,
aggregated over the GAEZ polygon; ≥95% valid area per property, no imputation.
This is not root-zone soil, annual soil observations or a farm soil test.

Original 124 retained cells supplied 124 labels **per crop**, 620 rows total:

| Crop | Zeros | Mean | Minimum | Median | 75th percentile | Maximum |
|---|---:|---:|---:|---:|---:|---:|
| BRL | 79 | 1255.702 | 0 | 0 | 1492.25 | 9998 |
| MZE | 77 | 1087.387 | 0 | 0 | 1628.75 | 9624 |
| RCD | 94 | 903.500 | 0 | 0 | 0 | 7865 |
| RCW | 92 | 695.363 | 0 | 0 | 414.75 | 6517 |
| WHE | 79 | 1265.169 | 0 | 0 | 1473.00 | 10000 |

Zeros are valid all-land suitability values, not NoData. None of these counts
establishes global agricultural representativeness. The reconstructed
distributions are descriptive; no test-only distribution or final-test error
was used for selection.

Original source URLs, crop rows and byte identities remain in
[`../phase4/evidence/source-audit.json`](../phase4/evidence/source-audit.json).
Reacquired source identities and metadata:
[`evidence/source-recovery.json`](evidence/source-recovery.json).
Attribution: FAO and IIASA (2025), GAEZ v5, CC BY 4.0; ISRIC SoilGrids,
CC BY 4.0; NASA POWER/MERRA2 environmental estimates.

### Completed expanded acquisition

The preregistered, target-independent supplement added 300 spaced cells from
the fixed seed-44 candidate pool. All **600 planned source cells / 3000 crop
labels** were processed, not a partially completed training file. **215 cells /
1075 aligned rows** remain: 215 real labels for each of the five crop types.
**385 cells / 1925 rows** were excluded: 294 insufficient native soil area,
91 no intersecting native tiles. No cells were replaced according to target
value or model performance. This expands aligned source cells by 73.4%, not by
counting the five crop rows as independent weather observations.

Retained extent: latitude −45.291667…74.958333, longitude
−160.791667…175.958333; **78 occupied 20-degree strata**, **215 conservative
coarse-environment groups**. These are sampling diagnostics, not a calibrated
global agricultural domain. The preparation cache contains 215 complete
2001–2020 POWER responses, five native soil VRTs and 1584 native soil tiles.
POWER was deliberately not downloaded for soil-excluded cells.

Counts, distributions and every exclusion:
[`evidence/expanded-quality.json`](evidence/expanded-quality.json).
Dataset and sample identities, including both canonical dataset hashes and
physical JSON-file SHA-256 hashes:
[`evidence/dataset-identities.json`](evidence/dataset-identities.json).
Restoration/source comparisons:
[`evidence/restoration-comparison.json`](evidence/restoration-comparison.json),
[`evidence/environment-source-comparison.json`](evidence/environment-source-comparison.json).

Acquisition completed in **2377.722 s (39 min 37.722 s)**, CPU **688.229 s**,
peak process RSS **587,600 KiB**. The research directory occupied
**732,606,087 bytes** at acquisition completion (includes source/cache,
datasets and small run files; not a measured network-transfer total). This
stayed inside the 45-minute / 1.5 GiB budget; no paid service or global catalog
collection was added. Only the five required index rasters and verified source
metadata were reacquired, not unrelated global layers. Resource evidence:
[`evidence/acquisition-summary.json`](evidence/acquisition-summary.json).

## D. Models and independent methods

Original recorded spatial results:

| Candidate | Buffered training CV MAE | Geographic validation MAE | RMSE | R² |
|---|---:|---:|---:|---:|
| Forest leaf 3 | 1294.336 | 1672.801 | 2535.843 | 0.057 |
| Forest leaf 8 | 1308.261 | 1720.740 | 2537.041 | 0.056 |
| Ridge alpha 1 | 1435.538 | 1800.651 | 2746.057 | −0.106 |
| Ridge alpha 10 | 1363.217 | 1772.500 | 2683.524 | −0.056 |
| Dummy mean | — | 1717.194 | 2635.068 | −0.018 |
| Train-only crop median (additional diagnostic) | — | 1347.125 | — | — |

The original selected model's per-crop MAEs were BRL 2026.640; MZE 1751.589;
RCD 1369.467; RCW 1265.771; WHE 1950.537. A lower rice MAE alone does not
establish acceptance: RCD improves its reconstructed crop-mean baseline only
about 4.7%, and RCW is worse than its crop-mean baseline (1125.784).

The recovery protocol is frozen in [`PROTOCOL.md`](PROTOCOL.md). It retains
seed-42 10-degree blocks, 150 km/shared-footprint purging, training-only
preprocessing and one-use final testing. It compares separate per-crop
mean/median baselines, Ridge, random forests and histogram gradient boosting,
with principal buffered spatial evaluation and diagnostic nonspatial
cell-grouped evaluation. New features, management scenarios and weakened
thresholds are not silently introduced.

### Actual restored-data per-crop recovery experiment

Executed on the authentically restored 124 cells, with separate estimators per
crop, 74/24/26 geographic source cells, all 25 declared candidate configurations
and both buffered spatial and diagnostic nonspatial cell-grouped CV. The table
shows each crop's validation-selected candidate, not an independent test result.

| Crop | Selected | Spatial CV MAE | Nonspatial CV MAE | Validation MAE | R² | Mean baseline MAE | Median baseline MAE |
|---|---|---:|---:|---:|---:|---:|---:|
| BRL | Forest leaf 8 | 1378.548 | 1447.599 | 2178.384 | 0.053 | 2055.981 | 1803.792 |
| MZE | Forest leaf 8 | 1236.524 | 1159.738 | 1535.550 | 0.190 | 1817.872 | 1537.750 |
| RCD | Forest leaf 3 | 779.814 | 692.064 | 842.937 | 0.500 | 1436.694 | 871.625 |
| RCW | Histogram | 549.374 | 606.700 | 781.060 | 0.158 | 1125.784 | 738.458 |
| WHE | Forest leaf 8 | 1404.582 | 1452.331 | 2011.453 | 0.014 | 2038.203 | 1784.000 |

Every crop was rejected **before final testing**: no diagnostic region met the
preregistered ≥10 training / ≥5 validation support screen. Separately, no crop
passes all global validation accuracy/baseline screens either: RCD improves
over its median baseline only about 3.3%, not the required 10%; RCW is worse
than median and misses R²; MZE misses MAE/R²/median gain; BRL and WHE miss
MAE/R²/baseline improvement. Do not reinterpret the improved RCD R² as an
accepted model or as permission to skip the independent final test.

All candidate/fold/region metrics, exact split and fold identities, source
manifest, library versions and decisions:
[`evidence/restored-evaluation.json`](evidence/restored-evaluation.json).
Elapsed **147.520 s**, CPU **150.169 s**, peak process RSS **352,992 KiB**.
No estimator was serialized, no final-test prediction was computed and no
holdout reservation was consumed.

### Actual expanded-data per-crop recovery experiment

The completed 215-cell dataset produced **135 train / 45 validation / 35 test
cells**, in **87 / 25 / 24 ten-degree blocks**, respectively. Every crop has
these same environmental cell identities; row counts are five times larger,
not additional independent environments.

| Crop | Selected | Spatial CV MAE | Nonspatial CV MAE | Validation MAE | RMSE | R² | Mean baseline MAE | Median baseline MAE |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| BRL | Forest leaf 8 | 1159.664 | 1010.181 | 2003.723 | 2742.216 | 0.036 | 2000.683 | 1942.467 |
| MZE | Forest leaf 3 | 999.031 | 990.694 | 1336.646 | 2114.089 | 0.259 | 1716.265 | 1565.467 |
| RCD | Forest leaf 3 | 606.365 | 525.547 | 595.670 | 1140.811 | 0.486 | 1263.876 | 614.200 |
| RCW | Forest leaf 3 | 546.122 | 427.252 | 663.310 | 1261.020 | 0.238 | 1022.525 | 591.511 |
| WHE | Forest leaf 8 | 1166.997 | 1018.478 | 1976.538 | 2816.485 | −0.018 | 2033.366 | 1972.956 |

**Maize passes the global development-set MAE/R²/baseline screens, but this is
not independent acceptance or a deployable domain.** The only count-eligible
regions were `lat4_lon1` (30–60°N, 120–60°W) and `lat4_lon4` (30–60°N,
60–120°E). They contain 13/6/1 and 18/6/4 train/validation/test source cells.
Thus even before environmental screening they have only **12 validation and
5 final-test cells combined**. The frozen range/joint-distance screen retains
just **4 of 45 validation cells (8.9%)**, in insufficient geographic blocks.

On those four retained development cells, maize MAE is **2429.711**, R²
**0.0386**; barley MAE **2157.794**; wheat **2642.540**. Both rice models have
zero error on four zero targets and **undefined R²**: that is an inadequate,
degenerate evaluation, not evidence of reliable rice predictions.

Every crop therefore fails support and/or accuracy gates **before final
testing**. Outside those count-eligible regions no domain is declared.
No final-test prediction, test-error calculation, reservation or estimator
serialization occurred. The 35-cell test remains untouched. Do not combine
the four supported-development cells with the 45-cell global validation
population to present a misleading accuracy/coverage claim.

Full 25-candidate results, fold/region errors, sample adequacy, every rejection
reason, coverage retention, dependency versions and exact identities:
[`evidence/expanded-evaluation.json`](evidence/expanded-evaluation.json).
Elapsed **298.939 s**, CPU **291.141 s**, peak process RSS **414,484 KiB**.

## E. Model acceptance

No original crop is validated for live predictions. Accuracy gates remain
MAE ≤1500, R² ≥0.2, ≥10% baseline improvement, regional MAE ≤2000 and adequate
independent geographic support. These are conservative project screens, not
FAO-endorsed precision standards. A numeric training range or a nearby
geographic block is not a validated reliability/confidence statement.

**Final recovery accepted scope: none.** The new genuine experiments do not
justify enabling any crop, country or management scenario in the live model
lane. The strongest development result (maize globally) does not overcome
inadequate independent domain evidence and poor error on the tiny retained
subset. Dryland rice's lower aggregate MAE still lacks 10% median-baseline
improvement and a nondegenerate supported-domain assessment.

The highest-value justified next correction is **prospectively dense,
geographically buffered sampling of a deliberately limited agricultural
domain**, beginning with the promising maize development result. Collect
enough complete source cells in persistent train/validation/test geography to
support ≥20 retained validation/test cells, six blocks and ≥5 cells per declared
region **after** coverage filtering. Preserve failed cells and avoid selection
on held-out targets. Separately review the soil footprint/coverage contract
using training/validation evidence; the five city checks below cannot provide
complete native soil vectors. If the contract changes, version it and refit/
validate it—never silently lower the 95% rule or fill missing soil with proxies.
Do not acquire another sparse global sample and claim its row count resolves
these demonstrated support failures.

## F. Artifacts and reproducibility

No accepted estimator/preprocessor artifact existed at recovery start:
the original rejection deliberately prevented serialization. Absence of a
rejected estimator is not evidence that a formerly accepted model was lost.

The new per-crop runner records immutable dataset/source/contract/version
identities, splits, folds, baselines, candidates, scope, coverage and decisions.
It serializes preprocessing together with an estimator only after independent
acceptance. No uploads, arbitrary client paths, or untrusted pickle/joblib
loading were added. Source hashes verify integrity, not operator authorship.

Reproduction:

```sh
export PYTHONPATH=artifacts/api-server
uv run python -m backend.machine_learning labels --root generated-artifacts/ml-recovery/labels
uv run python -m backend.machine_learning.recovery diagnose
uv run python -m backend.machine_learning.recovery acquire
# Train only a completed, original-source-replayable dataset:
OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 uv run python -m backend.machine_learning.recovery_training \
  --dataset generated-artifacts/ml-recovery/restored/dataset.json \
  --out generated-artifacts/ml-recovery/restored-training
uv run python -m backend.machine_learning.operational_checks
```

Do not rerun a completed acquisition/evaluation into the same evidence path or
delete a holdout ledger to obtain a new result. A partial progress file is
never training input. Ignored source caches are local, not a durable shared
research repository; this limitation must accompany any handoff.

## G. Backend inference

The existing `/api/analysis/model-status` correctly returns
`insufficiently_validated`, `predictionsEnabled: false`,
`phase4_validation_not_passed` and `missing_accepted_model`.
No rejected or synthetic estimator has been loaded into the live backend.
There is no new trusted live-model registration or prediction endpoint claim.
The historical builder does not bypass readiness or enable Stage B.

## H. Website

Existing farm → **AI Planner** → **AI crop-suitability availability** displays
the unavailable state. New/reopened planning reports retain their original
availability snapshot and explain that reference rules, published FAO
assessments and Field Shift trained predictions are different evidence lanes.
The FAO functionality present before recovery was preserved, not rebranded ML.

## I. Genuine inference examples

There was no qualified original model, so no genuine live prediction example
can be supplied from that experiment. A missing-model refusal is not model
execution, and a direct FAO raster value is not a trained prediction.

The expanded recovery also qualified **no model**, so there is deliberately
**no live model-generated prediction example, model artifact hash or execution
claim**. Genuine estimators did execute in the recorded training/validation
experiments; they did not execute as live farm predictions.

## J. Refusals and planner policy

Without an accepted model the planner receives **no ML values**, never a
zero or invented confidence. Agricultural reference rules, crop-family
rotation, farmer exclusions, water/soil conflicts and historical report
compatibility remain authoritative. No ranking is changed by unvalidated ML.

The builder refuses generic `rice`, non-LRLM management, invalid coordinates,
missing/ineligible native soil and incomplete historical climate. Rain-fed
irrigation alone is not confirmation of low-input management. No 2019–2025
dashboard values are relabeled as 2001–2020 features.

### Actual five-location historical and API results

All five checks acquired authentic **2001–2020 UTC NASA POWER** daily data at
their mapped GAEZ cell center, validated completeness/units and calculated all
24 climate features. None passed the unchanged required native soil-area
screen, so **no complete model vector was constructed** and no proxy was used.
The table's temperature/rain columns are genuine historical inputs, **not ML
predictions**; the reported soil fraction is rounded valid native area for the
first failing soil property, not confidence.

| Location | Exact selected latitude, longitude | January mean °C | January mean monthly rain mm | Reported soil valid fraction | Result |
|---|---|---:|---:|---:|---|
| Irbid | 32.55696, 35.8479 | 10.6443 | 92.4945 | 0.422 | Missing required native soil |
| Al Ain | 24.2249, 55.7452 | 18.0474 | 11.0585 | 0.000 | Missing required native soil |
| Colusa | 39.2146, −122.0094 | 8.1241 | 110.4910 | 0.932 | Missing required native soil |
| Stuttgart, Arkansas | 34.5004, −91.5526 | 4.5810 | 92.0920 | 0.922 | Missing required native soil |
| Córdoba | 37.8882, −4.7794 | 7.3359 | 45.6775 | 0.590 | Missing required native soil |

The missing-soil reasons are observed native mask results; this check does
not establish whether urban/water masks, missing tiles or other source
limitations caused each low fraction. Do not move a selected point to a
nearby soil proxy, lower the mask gate or return invented values to make a
demonstration succeed.

Five **real-data, rollback-isolated API flows passed**: create/open the exact
farm point, generate and reopen the persisted reference report, preserve its
availability/input snapshot, refuse ML values, and reject cross-session farm/
report read and report-write attempts with HTTP 404. The report correctly
retains 2019–2025 dashboard evidence separately from required 2001–2020 model
inputs. The new research historical builder is **not falsely presented as
connected live inference**. All test API mutations were rolled back.

Full genuine inputs/provenance, mapped coordinates and refusals:
[`evidence/five-location-historical.json`](evidence/five-location-historical.json).
API/persistence/isolation results:
[`evidence/five-location-api.json`](evidence/five-location-api.json).
These named locations are operational demonstrations, **not an independent
accuracy benchmark**, and none executed an estimator as a farm prediction.

As a positive software control, a real retained source cell was selected and
the requested point deliberately offset by 0.001° within that same cell.
The historical builder preserved the exact selected point, mapped the training
cell correctly and produced all **29 numeric features with maximum difference
0.0** from the genuine training record. It still returned an honest missing-
approved-model refusal. This distinguishes real missing-soil refusals at the
five cities from an always-failing or mock-only builder. Evidence:
[`evidence/complete-input-control.json`](evidence/complete-input-control.json).

Any future planner activation must retain hard agricultural constraints and
persist model/dataset/contract/scope/input identities in the report. Even an
accepted index is only evidence about GAEZ modeled suitability; it must not
override crop exclusions, rotation conflicts, water/soil limitations or farmer
operating constraints. That future policy is not claimed as currently active.

## K. Executed checks and resource use

The preservation baseline ran **179 Python tests, all passed**, in 29.946 s
against rolled-back development transactions. No migration, seed overwrite or
production database operation was used. Existing isolation is a signed
**browser-owned cookie session**, not account authentication or cross-device
identity. That distinction applies to every browser/security result.

API code generation and workspace typecheck passed. Frontend production build
initially failed because the standalone shell omitted managed `PORT` and
`BASE_PATH`; with `PORT=5000 BASE_PATH=/ NODE_ENV=production` it passed, with
the existing >500 kB chunk-size warning. The three frontend retry tests passed.
This was an invocation/environment requirement, not an application code fix.

| Executed command/check | Actual result |
|---|---|
| `OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 PYTHONPATH=artifacts/api-server uv run python -m unittest discover -s artifacts/api-server/tests -v` | Recovery suite **195 passed in 32.529 s** |
| `OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 PYTHONPATH=artifacts/api-server uv run python -m unittest discover -s artifacts/api-server/tests -p test_machine_learning.py -v` | **40 ML software tests passed** after the holdout change |
| `PYTHONPATH=artifacts/api-server uv run python -m unittest discover -s artifacts/api-server/tests -p test_ml_recovery.py -v` | **16 recovery tests passed**, including final coordinate-identity assertions, in 1.773 s |
| `pnpm --filter @workspace/api-spec run codegen` | Passed; existing FAO contracts preserved |
| `pnpm run typecheck` | Passed across workspace libraries, API, Field Shift and mockup |
| `PORT=5000 BASE_PATH=/ NODE_ENV=production pnpm --filter @workspace/field-shift run build` | Passed; existing large-chunk warning |
| `node --test artifacts/field-shift/src/lib/environment-retry.test.ts` | **3 passed**, 0 failed |
| `PYTHONPATH=artifacts/api-server uv run python scripts/verify_ml_recovery_api.py` | **5 real-data location flows passed**; all mutations rolled back |
| Managed API workflow restart + `/api/analysis/model-status` | Clean startup, HTTP 200, predictions disabled |
| Public app screenshot | Homepage rendered, no application/browser error |
| Single browser pass: five farm/report/reopen journeys plus separate-session access checks | **5/5 passed**, no console/API errors |

The software tests use explicitly synthetic test-only fixtures where required;
those fixtures are not scientific training data or live predictions. The
real-data evaluation and five-location evidence are separate artifacts.
Security checks cover session ownership, cross-owner refusals, bad input,
source/schema incompatibility, artifact integrity and prevention of untrusted
loading; no separate dependency/SAST security-scan claim is made.

Before/after rolled-back regressions, the preserved tables contained:
**6 farms, 0 saved observations, 143192 environmental values, 4 soil estimates,
1 farmer measurement, 4 saved reports and 2 rotation drafts**. Counts were
unchanged; see [`evidence/database-preservation.json`](evidence/database-preservation.json).
The browser pass created only five explicitly marked test farms (227–231)
and reports (118–122). Their exact IDs **and** names were verified before
deleting only those test records. There were no test observations, measurements
or drafts to delete. All seven original table counts were restored exactly;
the cleanup evidence is appended to the same preservation record.

### Browser observations and limits

| Location | Browser result |
|---|---|
| Irbid | Unavailable lane rendered; reference report saved and reopened; withheld disclosure checked |
| Al Ain | Same; separate published FAO lane visible |
| Colusa | Same; management/spatial-soil incompatibility reasons visible |
| Stuttgart, Arkansas | Same unavailable/report/reopen flow passed |
| Córdoba | Same; missing-soil reason remained explicit |

All five reports stated: **“Reference rules only. No model predictions were
supplied or used to rank rotations.”** The per-crop lines showed insufficient
evidence, not numeric model predictions. A second independent browser context
received HTTP 404 for the farm, report list and specific report; the original
context received HTTP 200. This tests browser-workspace isolation, **not account
authentication**.

Reopen/disclosure checks used rendered text presence; the live lane's own
withheld disclosure was not separately expanded. The published FAO lookup,
unrelated map/editing paths and an accepted-model journey were not exercised.
No accepted model exists to exercise. The separate FAO integration's existing
regressions are not a substitute for an ML execution claim.

Machine-readable browser evidence:
[`evidence/browser-results.json`](evidence/browser-results.json).
Captured screenshot references: `lr0kx8` (live unavailable), `6zeffe` (saved
withheld disclosure), `ekvi1j` (separate FAO lane), `77ml1f` (saved report).
The test-only records were removed after these captures, so their farm URLs
are not ongoing review links.

Raw verified research objects remain under ignored
`generated-artifacts/ml-recovery/`; they are **not a durable shared store** and
must not be assumed to accompany a task merge or fresh workspace. Small
reports, hashes, protocols and the geographic holdout ledger are versioned.
Prospective dense-domain validation and approved durable research storage
were proposed as separate follow-ups; neither is claimed as implemented.

## L. Deployment status

At both the initial and final verified deployment checks this fork had **no
active production deployment**. No publication was requested or performed. Work remains on the
isolated review branch, not merged into main. Training, acceptance, backend
loading, API exposure, website display and planner use are separate statuses;
successful code tests do not imply scientific validation or activation.

| Stage | Verified status |
|---|---|
| Authentic source recovery and expanded preparation | Completed, 600 planned / 215 aligned cells |
| Genuine estimators trained/executed in research | Yes: original pooled replay and two per-crop experiments |
| Independent model acceptance | **No crop/domain qualified; final test not evaluated** |
| Accepted model/preprocessing artifact | None; no hash fabricated |
| Trusted model loaded in live backend | No |
| Live ML prediction API exposed | No; readiness/refusal/report APIs remain operational |
| Website genuine ML outputs displayed | No; explicit availability/refusal and independent FAO/reference lanes |
| ML used to rank agricultural plans | No; agricultural constraints and existing rules preserved |
| Exact-period historical research builder | Implemented and exercised at all five locations; soil refused all five |
| Integrated into main | Not merged at the time this fork's evidence was captured |
| Production publication/deployment | **Not performed** |
