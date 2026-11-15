# Field Shift Phase 4 — factual implementation report (A–J)

Date: November 15, 2026.

**Delivery status: genuine supervised training completed; candidates rejected
on geographic validation. This is not a completed scientific Phase 4 release.
No accepted model is bundled or activated, and the final test remains untouched.**

Authoritative run counts and reasons are captured in
[`evidence/run-summary.json`](evidence/run-summary.json),
[`evidence/quality.json`](evidence/quality.json), and
[`evidence/training-evidence.json`](evidence/training-evidence.json).
Large original rasters, API responses and the full feature dataset remain in
the ignored local research directory and can be reacquired using saved URLs,
hashes and commands. This report does not claim those ignored files are
automatically shared or durably hosted after this task.

## A. Implementation summary

Built a standalone, file-only Python package under
`artifacts/api-server/backend/machine_learning`:

* verified official FAO metadata/catalog ingestion, authentic raster acquisition
  and a checked manual importer;
* bounded/retryable/resumable HTTP downloads with provenance and immutable cache
  verification;
* reproducible geographic sampling of actual label cells;
* independent 2001–2020 NASA acquisition and mask-preserving native SoilGrids
  subsetting/aggregation;
* complete-case dataset assembly, replay validation and explicit exclusions;
* shared versioned features/preprocessing contract;
* seeded spatial train/validation/test partitions, coarse-footprint purging,
  geographic buffering, and training-only buffered CV;
* dummy and crop-mean baselines, Ridge/Random Forest candidate training,
  predeclared acceptance gates, single-use final holdout and accepted-only
  estimator serialization;
* typed standalone prediction input, compatible-model checks and structured
  unavailability without scores;
* source fixtures, executable tests, model card, reproduction instructions
  and a non-invasive Phase 3 adapter specification.

No Phase 3 rules, recommendation engine, environmental services, farm/map UI,
live endpoint, database schema, production data or deployment was changed.
The only shared runtime updates are the required scientific dependencies,
their lock entries, and Nix expat needed to import rasterio in this environment.
The existing planner remains reference based.

## B. Genuine data sources obtained

### Existing archive audit

All four original CSVs were located and matched byte-for-byte to the supplied
archive: NASA daily 10,228 rows, monthly 336, POWER modeled wetness 10,228,
nearby proxy soil four rows. Four demonstration sites; NASA 2019–2025.
They remain ineligible as aligned suitability-training evidence.

### Authentic FAO GAEZ labels

Retrieved the official RES05 workbook, official machine-readable dataset
metadata, and five complete authentic **RES05-SXX** suitability GeoTIFFs.
Each has 3,259,820 valid cells. The pilot samples 180 geographically
distributed cells × five crop types = **900 genuine source labels**.
This is not 900 independent environmental observations.

Verified: GAEZ v5 framework; catalog edition “Version 2.0”; AgERA5 historical
2001–2020; rain-fed/low-input LRLM; Wheat, Barley, Maize, Dryland rice and
Wetland rice. Index 0–10,000, scale 1, NoData −9, EPSG:4326, five arc minutes,
approximately 10 km. CC BY 4.0; attribution FAO and IIASA, GAEZ v5 (2025).
Generic rice is not silently mapped to either source type.

After the initial readiness failure, a **preregistered, target-independent**
120-cell supplement expanded the planned sample to **300 cells / 1,500 authentic
crop-cell labels**. Its 60/40/20 test/train/validation geographic allocation,
seed 43 candidate pool and spacing rules are in `SUPPLEMENT_PROTOCOL.md`.
No model error or final-test performance was used to select those locations.

### Environmental acquisition

Genuine NASA POWER MERRA2/AG/UTC daily responses for 2001–2020 and official
ISRIC SoilGrids native mean VRTs/intersecting 250 m tiles were obtained.
The completed run summary records downloaded response and tile counts.
Soil depth is 0–5 cm; masked pixels are retained. SoilGrids is CC BY 4.0;
retain ISRIC attribution. NASA POWER use/acknowledgement guidance is linked
in `SOURCES.md`.

REST probes returning null soil values and WCS subsets without unambiguous
NoData metadata were rejected, not used as substitute measurements.
Native WebDAV acquisition is the successful alternative.

Exact links, bytes, acquisition times, selected crop/scenario rows, archive
comparison and SHA-256 identities:
[`evidence/source-audit.json`](evidence/source-audit.json).
Scientific definitions and access limitations: [`SOURCES.md`](SOURCES.md).

## C. Training readiness

A genuine pilot dataset is assembled only from authentic label values and
complete matched environmental inputs. Soil masking and other explicit
source/quality failures exclude the whole cell across crops.
No farmer request, rule-generated target, proxy soil row or synthetic label
is accepted by preparation.

The actual number of aligned cells/rows, all exclusion reasons, geographic
extent, label distribution and conservative coarse-environment coverage are
in the quality report. The recorded readiness result—not raw label count—
determines whether fitting is allowed.

**Initial pilot:** 95 aligned source cells / 475 crop-cell rows, with 63/21/11
train/validation/test cells. This failed the overall and test readiness floors;
no models were fitted on that initial pilot.

**Actual completed supplemented dataset:** 124 aligned source cells / 620
crop-cell rows; 176 cells / 880 rows excluded. Of the exclusions, 138 cells
had less than 95% valid native soil area and 38 had no intersecting native
soil tiles. There were no fabricated replacements. The retained set spans
73 geographic 20° strata and 124 conservative coarse-environment groups; these are coverage
diagnostics, not proof of global representativeness or statistical independence.

The final deterministic partitions contain **74 train, 24 validation and 26
test cells** (370/120/130 rows). All frozen readiness gates passed. The real
training command then fitted the baselines and four candidate configurations.
All 300 complete historical POWER responses, five native soil VRTs and 870
downloaded native soil tiles remain traceable in the local research cache.

The predeclared minimum is 120 source cells overall, 60/20/20 in
train/validation/test, six geographic blocks per partition, all crop types,
and adequate train/validation label span. These are screening floors, not a
global statistical-power guarantee. The bounded 180-cell pilot does not
justify treating missing soil pixels, repeated crops or nearby grid samples
as extra independent evidence. Thresholds were not relaxed to make a model.

## D. Model results

**There is no accepted production-trained model or validated predictive crop
coverage in this delivery.** Read the exact readiness/rejection outcome in
`evidence/run-summary.json`.

For this run specifically: a dummy mean baseline, crop-mean parameters and
**four genuine candidate configurations were fitted** on 74 training cells.
Training-only buffered three-fold CV and 24-cell geographic validation were
actually run. The best candidate failed the predeclared validation MAE ≤1,500
gate, so **no final-test metric was computed and no model file was saved**.

| Candidate | Validation MAE | Validation RMSE | Validation R² |
|---|---:|---:|---:|
| Random Forest, leaf 3 | **1,672.801** | 2,535.843 | 0.057 |
| Random Forest, leaf 8 | 1,720.740 | 2,537.041 | 0.056 |
| Ridge, alpha 1 | 1,800.651 | 2,746.057 | −0.106 |
| Ridge, alpha 10 | 1,772.500 | 2,683.524 | −0.056 |
| Dummy mean baseline | 1,717.194 | 2,635.068 | −0.018 |

MAE/RMSE are **GAEZ index points**, not percentages or probabilities.
The best candidate improves validation MAE over the dummy by only about 2.6%;
this is weak approximation, not a reliable farm model. Selected-candidate
validation MAE by crop: Barley 2,026.640; Maize 1,751.589; Dryland rice
1,369.467; Wetland rice 1,265.771; Wheat 1,950.537. Each has 24 cells.
Sixteen diagnostic geographic regions have only 1–3 validation cells each;
some errors exceed 3,000–4,600 points. These are major support/error weaknesses,
not verified climatic-zone results.

Full actual CV fold, aggregate, crop and region metrics:
[`evidence/evaluation.md`](evidence/evaluation.md) and `training-evidence.json`.
The 26-cell final test was **not consumed**: a failed validation gate is a
reason to reject, not to inspect the final test hoping for a better number.
There is no accepted predictive crop coverage. Temporary synthetic test models
remain separate from these genuine supervised results.

## E. Files and modules

| Component | Purpose |
|---|---|
| `common.py`, `download.py` | Hashes, atomic JSON, bounded/resumable cached HTTP |
| `labels.py` | Official catalog semantics, imports, raster checks, geographic samples |
| `environment.py` | Independent historical POWER and native/WCS SoilGrids acquisition |
| `dataset.py` | Aligned assembly, exclusions, quality, original-source feature replay |
| `contract.py`, `config.json` | Feature/target versions and preregistered readiness/acceptance |
| `spatial.py` | Seeded blocks, source-footprint/geodesic buffering and CV purging |
| `training.py` | Baselines, candidates, independent evaluation, accepted-only packaging |
| `inference.py` | Typed-input standalone prediction and all unavailable/unsupported paths |
| `audit.py`, `evidence.py`, `__main__.py` | Reproducible CLI and factual evidence snapshots |
| `supplement.py`, `SUPPLEMENT_PROTOCOL.md` | Frozen, target-independent additional geographic sampling |
| `tests/test_machine_learning.py` | Offline software tests, explicitly isolated synthetic fixtures |
| `tests/fixtures/phase4` | Small attributable authentic label/window fixtures |
| `docs/phase4` | This A–J report, source audit, reproduction, model card and adapter |
| `pyproject.toml`, `uv.lock`, `.replit` | Narrow scientific/runtime dependency additions |

Paths in the first nine rows are relative to the new ML package. Existing
application modules were inspected but not edited. The small persistent
scientific-source note records the non-obvious WCS mask behavior.

## F. Reproducible inference demonstration

The saved example request uses **actual aligned environmental feature values**
from this run, not an invented farm example. The authoritative source label,
if present in the dataset, remains separate from any prediction.

```sh
PYTHONPATH=artifacts/api-server uv run python -m backend.machine_learning \
  predict --request docs/phase4/evidence/example-request.json
```

The current availability response is saved in
[`evidence/example-response.json`](evidence/example-response.json). With no
accepted model it reports `unavailable`, `missing_accepted_model`,
`available: false`, target/unit/period/limitations, and **no prediction field**.
Exit code 2 is intentional. This is an actual tested availability result,
**not an actual trained-model prediction**.

## G. Executed checks

* Final existing Python regression suite plus new ML tests: **120 tests passed**,
  including **40 ML software tests**.
  Includes rollback-isolated existing farm/environment/planner API tests.
* `pnpm run typecheck`: passed across libraries, API, Field Shift, mockup and
  scripts.
* API workflow restarted after the dependency/code batch: clean startup.
* Existing public frontend loaded successfully in a screenshot; no visible
  application breakage or browser errors. No frontend behavior was changed.

Tests cover authentic fixture parsing, corrupt/missing files, provenance/cache
hashes, bounded retries/range resumption, coordinates/CRS/NoData, native tile
subsetting, soil units, complete leap-year climate aggregation, missing values,
period/unit/schema mismatches, duplicates, split reproducibility/leakage,
buffered CV, baseline/metrics, preprocessing isolation, accepted-only
serialization, once-only holdout and inference success/failure paths.

Synthetic test artifacts are created only in temporary directories. No
browser-based sign-in/payment testing was necessary: those paths were not
changed. No production mutation or migration was performed.

## H. Phase 3 integration

Exact interface, field names, units, examples, statuses and safety constraints:
[`ADAPTER.md`](ADAPTER.md).

Import `PredictionInput` and `SuitabilityPredictor` only in a later reviewed
adapter. No accepted model currently exists; the safe configuration is
`directory=None`. Do not connect the live planner during this task.

The existing Phase 3 feature builder's 2019–2025 period and possibly
farmer-reported/proxy soil are incompatible with this model contract.
Do not relabel them as aligned 2001–2020 data. Phase 3 remains responsible
for calendars, water balance, history, rotation rules and management advice.

## I. Limitations

This learns to approximate a modeled assessment, not observed farm outcomes.
POWER and AgERA5 differ; topsoil estimates are static and shallow; coarse
climate/labels do not deliver field precision. The geographically spread
pilot is neither a global benchmark nor verified climatic-zone coverage.
Complete-case soil screening can create selection bias. Unrepresented
environments are not crop-failure labels.

Current predictive coverage is empty. Any future accepted model is restricted
to its validated crop/scenario/period/feature contract and conservative joint
environmental/geographic support. No confidence percentage, worldwide claim,
farmer-assertion verification, or complete Phase 5 reliability claim is made.

Large ignored research files are local; Git contains the code and small
review evidence, not an automatically durable global data service.
Hashes provide integrity, not protection against malicious operator-provided
pickle files; trusted artifact handling is required.

## J. Remaining work

**Phase 4 remains scientifically unfinished despite genuine training:** improve
the weak approximation using additional independent aligned environmental
coverage and justified features/source matching; declare changes before
evaluation; pass the unchanged validation and untouched geographic acceptance
process; and obtain scientific/operator review. Any further model development
must use training/validation only. Do not weaken gates, invent soil values,
or inspect/reuse the final holdout until an estimator appears acceptable.

Phase 5 then needs independent validation of environmental similarity,
coverage/reliability and sparse-region failure behavior. Source-derived
model error must not become invented certainty.

Only after a genuine accepted artifact and explicit approval should another
task implement guarded API/UI integration, trusted artifact distribution,
operational monitoring and any live activation. Publication is not part of
this task. Crop calendars and crop-season water balance remain the separately
planned work and were not implemented here.

Full reproduction and precise manual-file requirements:
[`REPRODUCE.md`](REPRODUCE.md). Stop here for explicit review; do not merge,
activate or deploy automatically.
