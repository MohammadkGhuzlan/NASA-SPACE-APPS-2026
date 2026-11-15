# Current policy

This document records the earlier experimental-only delivery. The user later
explicitly approved estimated soil inputs, normal workflow activation and saving
unvalidated outputs in normal reports. Those earlier access/input/report
restrictions are superseded by [Unvalidated workflow](UNVALIDATED_WORKFLOW.md).
Scientific validation has **not** been passed; no publication was authorized.

# Field Shift — experimental ML mode

## Scope and safety

This development-only pathway runs genuine failed research estimators. It does
not accept them for production, alter validation thresholds or place their
outputs in agricultural recommendations. The normal readiness endpoint remains
disabled. No production publishing is authorized or performed.

The UI displays:

> Experimental model — failed validation. Predictions may be inaccurate and should not be used for real farming decisions.

At the user's subsequent request, **all development-preview users may use this
lane**, but only for farms in their own signed browser workspace. No account
authentication or ownership-sharing capability was added. Production runtime
always refuses this lane.

## Authentic artifact recovery

The merged 600-sampled-cell experiment retained 215 complete environmental cells,
with five crop rows per cell: 1,075 rows, not 1,075 independent environments.
The original selected estimators were deliberately not serialized after rejection.
The original ignored dataset/cache was not transferred by the merge either.

Restoration:

- Reacquired the five exact RES05-SXX label rasters and verified original hashes.
- Reconstructed original sampling and verified all 215 retained cell identities.
- Reused the recorded 385 exclusions instead of repeating their requests.
- Restored complete genuine 2001–2020 NASA and native-soil evidence for the
  retained locations in **1,125.114 seconds**.
- The reconstructed dataset's hash is
  `53c88a5c03b293dfbd7c764f981769284d26e1ea5b9a3295380c53f1138f4f25`.
  The original hash was
  `1b3e36d6c0307fc583bbf22b522d6e44f3c659967b951814ebd9219318d2c030`.
  Acquisition timestamps and provenance changed; the old identity was not forged.

The reproduction operator verifies original-source feature replay and exact
135/45/35 train/validation/test cell membership, then fits only the five
previously selected models on the **135 training cells per crop**. No
hyperparameter search is repeated. Development MAE/RMSE/R² must reproduce the
recorded run within 0.000001 before the experimental manifest is published.

The preprocessing pipeline is serialized together with each estimator.
Artifact checks include SHA-256, crop, target, feature order, dataset identity,
scientific contract and exact package versions. Only fixed local
operator-produced paths are loadable; no web upload/path or trusted-feature
claim is accepted. Hashes establish integrity, not the safety of arbitrary
third-party pickle files.

Files are under `generated-artifacts/experimental-ml/models/` with an immutable
manifest and the explicit filename suffix `-experimental.joblib`.
Neither the old nor the restored final test is predicted or scored.

## Models and interpretation

These are the recorded **global development-validation** metrics on 45 cells,
before the geographic support screen—not final-test or local-farm accuracy:

| Crop | Selected model | MAE | R² | Mean baseline MAE | Median baseline MAE |
|---|---|---:|---:|---:|---:|
| Barley BRL | Forest leaf 8 | 2003.723 | 0.036 | 2000.683 | 1942.467 |
| Maize MZE | Forest leaf 3 | 1336.646 | 0.259 | 1716.265 | 1565.467 |
| Dryland rice RCD | Forest leaf 3 | 595.670 | 0.486 | 1263.876 | 614.200 |
| Wetland rice RCW | Forest leaf 3 | 663.310 | 0.238 | 1022.525 | 591.511 |
| Wheat WHE | Forest leaf 8 | 1976.538 | −0.018 | 2033.366 | 1972.956 |

Every crop is **rejected before final testing**. The development support screen
retained only four cells, too few to establish the required geographic accuracy.
Even a technically in-screen output has no validated geographic domain.
Out-of-screen but complete inputs are allowed only with an explicit
`out_of_domain` warning.

Target: approximation of FAO/IIASA GAEZ v5 **RES05-SXX** modeled all-land
suitability, **0–10,000 index points**, rain-fed low-input **LRLM**, historical
2001–2020. These are not probabilities, yield, profit, planting advice or
rotation benefits. The original prediction helper's range restriction is
preserved. Published **RES05-SIX** class lookups remain a separate source lane.

## Environmental input contract

The exact selected coordinate maps to its containing five-arc-minute GAEZ cell.
The model uses complete UTC 2001–2020 monthly climate features from the cell
center and native ISRIC SoilGrids mean properties over that cell, 0–5 cm.
The original missing-data and 95% usable-soil-area rules are unchanged.

The NASA feature product is POWER/MERRA2; GAEZ labels use AgERA5. Equal years
do not make them the same climate product. Neither nearby proxy soil estimates,
farmer claims nor the 2019–2025 dashboard inputs substitute for model features.
Missing required soil features still prevent inference in experimental mode.

## Backend and UI

New backend package: `backend/experimental/`.

- Owner-scoped GET/POST `/api/farms/{id}/experimental-ml`.
- Owner-scoped GET `/api/farms/{id}/experimental-ml/jobs/{jobId}`.
- Explicit warning acknowledgment, fixed crop identifiers and server-owned
  coordinates; no arbitrary paths, vectors, URLs or scenario overrides.
- One active lookup globally, 30-second per-workspace admission cooldown,
  hard 300-second acquisition subprocess bound, source-byte budget,
  source-object cache reuse and at most 256 disposable experimental jobs.
- Structured missing-input, artifact-failure, interrupted-job and moved-farm
  refusals. Session ownership applies even though all development users may run
  experiments.

The farm's **Rotation planner** now includes **Experimental ML predictions**.
Users explicitly choose a crop, acknowledge the warning and run a model.
The section displays actual output, units, rejected-model metrics, input
provenance, source-cell mapping, model/dataset/artifact identity and support
limitations. No crop ranking or confidence percentage is generated.

Client job progress polls only while preparing; explicit retries refresh the
same job's query cache. The last selected crop and opaque job ID survive a
reload in session storage, but do not trigger a new prediction automatically.
Feature vectors, credentials and results are not stored in browser storage.
The production-report database and recommendation engine are unchanged.

## Operator commands

From the workspace root:

```sh
export PYTHONPATH=artifacts/api-server
# Restore missing inputs only; matching objects are reused.
uv run python -m backend.machine_learning.experimental_restore
# Refuses to repeat fitting once the experimental manifest exists.
uv run python -m backend.experimental.operator reproduce
# Current user-requested development access policy:
uv run python -m backend.experimental.operator open-development
# To close public preview access later:
uv run python -m backend.experimental.operator restrict-development
# Optional restricted browser-workspace approval:
uv run python -m backend.experimental.operator authorize --farm-id FARM_ID
# Real API and pipeline checks, with isolated synthetic farm profiles only:
uv run python scripts/verify-experimental.py
```

Runtime defaults to locked without the local operator-access file or outside
`NODE_ENV=development`. Operator files and model/source binaries are ignored by
Git and excluded from deployment. They are local caches, **not durable
cross-workspace storage**; a clean workspace must not claim models are ready.

## Verification evidence

The exact operational results are generated in
`generated-artifacts/experimental-ml/verification.json`: source-complete
positive control, all five requested locations, real crop-pipeline execution,
cross-session 404 checks and unchanged production readiness.

The software regression checks cover operator grants, broad development access,
production refusal, ownership isolation, integrity-before-deserialization,
missing features, strict request bodies, required acknowledgment, concurrency,
stale/moved jobs and disposable-cache limits. Software fixtures are not training
data or production output examples.

### Executed results

- Full backend regression suite: **215 tests passed**.
- Frontend retry tests: **3 passed**.
- OpenAPI regeneration, shared-library compilation and Field Shift TypeScript:
  passed.
- Real operator/API checks used no response interception, synthetic training
  vectors or hardcoded prediction fallbacks.
- Six real API jobs (complete-input control plus five requested locations)
  completed, with another-session access returning **404** for each farm.
- All five serialized crop pipelines were separately executed on re-prepared
  authentic control inputs. Results: BRL 443.1318614022888, MZE
  172.43023015873015, RCD 0, RCW 0, WHE 464.51522297636996 index points.
  The two zero values are actual estimator outputs, not missing-data fills.
- An additional authentic, complete-input control outside the development
  support screen returned **1643.8219427609422** index points and
  `out_of_domain`. It was selected from recorded training-cell membership by
  geography, not target/model error; it is not an accuracy benchmark.

All five requested locations retrieved genuine required-period climate
features, but **none had a complete eligible native-soil vector**:

| Location | 2001–2020 climate | First failing soil layer's valid-area fraction | ML output |
|---|---|---:|---|
| Irbid | Retrieved | 0.422 | Withheld: missing required input |
| Al Ain | Retrieved | 0.000 | Withheld: missing required input |
| Colusa | Retrieved | 0.932 | Withheld: missing required input |
| Stuttgart | Retrieved | 0.922 | Withheld: missing required input |
| Córdoba | Retrieved | 0.590 | Withheld: missing required input |

The unchanged usable-area requirement is 0.95. These fractions describe a
modeled raster mask, not farm soil quality or agricultural suitability.
The location checks requested MZE; the missing soil features are shared
requirements of all five crop models. Experimental mode does not fabricate
them for another crop.

### Browser verification

A fresh browser created only isolated test farm 212 and ran the actual MZE
workflow. It verified explicit selection and acknowledgment, real POST/job
polling, estimator execution, the **172.43023015873015 Index** result, hashes,
version, source-cell provenance and rejection warnings. Reload restored the
job with GET only; changing crop removed the stale result without submitting
a new prediction. FAO and production-readiness sections stayed separate;
production predictions remained false. No page JavaScript errors occurred.

The initial mobile check found the long numerical value overflowing its card.
Wrapping and mobile type sizing were corrected. The focused 402×874 recheck
passed: value and metadata stayed inside the card, document width was
387/387 pixels, and no new POST or record creation occurred. The full-precision
number wraps across lines on narrow screens, a remaining cosmetic limitation.

### Preservation and deployment status

No original rows were deleted. Hashes of the **161,091 original environmental
values, nine environmental locations, four soil estimates and four existing
saved reports** remained unchanged.

There was concurrent preview activity: one of eight original farm hashes
changed and two additional normal reports appeared during this run. This
hash-only comparison cannot attribute that farm change. The experimental
module and verification harness do not update existing farm profiles or
generate normal reports; they added seven isolated synthetic test farms only.
Accordingly this report does **not** falsely claim all original farm hashes
were unchanged.

Implementation is on `experimental-ml-mode`; it has not been merged into main
or published. Genuine experimental artifacts are present and served in this
development workspace. **No crop is validated or accepted for production.**

Remaining blockers: incomplete native-soil inputs at the five named sites,
failed geographic/accuracy acceptance, and local-only model/source-cache
storage. These are not resolved by opening development access.
