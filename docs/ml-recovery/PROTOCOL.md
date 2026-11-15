# Frozen recovery protocol

Declared before recovery environmental preparation, fitting or final evaluation.
The previous validation results are known; its final-test labels have not been
evaluated. This is a bounded recovery experiment, not a worldwide benchmark.

## Source and feature contract

Keep `gaez-approximation-1`: 24 monthly POWER temperature/precipitation
features for 2001–2020 UTC, plus five native masked SoilGrids 0–5 cm cell-area
means; continuous GAEZ v5 RES05-SXX HP0120 AGERA5 HIST LRLM labels for WHE,
BRL, MZE, RCD, RCW. Keep valid zeros. Never substitute RES05-SIX classes.
POWER/MERRA2 is a different climate product from GAEZ/AgERA5; aligned years
do not establish interchangeable climate inputs. No causal claim of a unit,
crop-mapping or period bug is justified by the previous metrics.

## Sampling, immutable partitions and final holdout

Reconstruct the original seed-42 180-cell sample and seed-43 120-cell supplement
from byte-verified original label rasters. Compare retained identities to the
recorded splits before fitting. Keep every original exclusion for comparison.
If source identities differ, stop and report rather than claim reproduction.

Retain seed-42 10-degree block assignment, 150 km and shared POWER-footprint
purging; all five crops from a source cell stay together. Holdout identity is
the source product/scenario/period, seed and spatial block, NOT a dataset hash.
Record a shared, exclusive block reservation before any final test; a different
dataset path/hash must not allow the same geography to be tested again.

First restore the 300 planned cells. Then, only within the same resource budget,
add at most 300 target-independent, seed-44 spaced cells from a fixed 1800-cell
candidate pool, excluding all existing points within 150 km/shared footprint.
No soil availability or target values determine replacement. New cells use the
same geographic assignment, not a new random split. Keep failures explicit.
The five named demonstration locations are operational checks only, never
selection or acceptance data.

## Models and eligibility

Compare per-crop mean and median dummy baselines, Ridge (alpha 1, 10), random
forest (150 trees, leaf 3, 8) and histogram gradient boosting (100 iterations,
leaf 15, L2=1). Training-fold-only StandardScaler; no imputation. Fit separately
by crop, not a single cross-crop acceptance decision. Three training-only
buffered spatial folds are principal diagnostics; grouped non-spatial folds
keep shared environmental cells together and are diagnostic only.

For each crop, choose the candidate by spatial validation MAE, without looking
at final test. Validation AND test must independently pass the unchanged
screening accuracy standards: MAE ≤1500 index points, R² ≥0.2, ≥10% improvement
over both mean and median baselines. Crop error must also be ≤1800; each
eligible diagnostic geographic region must have ≥5 cells and MAE ≤2000.
At least 60/20/20 independent train/validation/test cells, six blocks per
partition, and ≥3000 train/validation target span are retained as screening
floors, not statistical power guarantees. Report all failing gates at once.

Domain eligibility is fixed from training/validation support before final
evaluation: only diagnostic regions with ≥10 training and ≥5 validation cells
can be considered. A region with insufficient support is **excluded from the
declared deployment domain**, never silently included as validated. A crop
with no eligible domain is not tested or serialized. No lowering thresholds
to rescue rice or other crops. Scope choice and unsupported regions are saved.

Coverage is a refusal screen, not confidence: training numeric ranges plus
train-scaled nearest-environment distance, calibrated only on validation in
eligible regions. The 95th percentile distance is frozen before final testing;
report coverage retention and error on the retained validation/test population.
Do not call an entire tested block supported merely because it contains one
test point. Final acceptance concerns the exact retained domain and must
satisfy its sample floors. No calibrated probabilities.

## Resource and stop rules

One acquisition process, two workers, ≤45 minutes and ≤1.5 GiB cache, no paid
services; download retries/individual byte caps remain bounded by existing
clients. Two-minute per-candidate fitting budget is a reporting target; bounded
candidate counts and tree sizes are the hard limits. Save elapsed time, CPU,
peak RSS, bytes and completion state. Stop at resource/source/adequacy failure;
never call a partial preparation complete. Preserve acquired bytes and sidecars.
No production mutation, migration, model upload or publication.

Only an independently accepted crop/domain can proceed to trusted live bundle
loading and planner activation. If none qualifies, retain the existing explicit
website refusals and reference/FAO lanes; document the highest-value next
correction and the exact missing evidence rather than install a test estimator.
