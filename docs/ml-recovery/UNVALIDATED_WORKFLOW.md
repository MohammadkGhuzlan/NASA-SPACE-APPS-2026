# Enabled unvalidated predictions with estimated soil

## User-approved scope

The user requested enabling model inference despite inaccuracy and explicitly
selected **“Allow estimated inputs with warnings.”** Operational inference is
now enabled in the normal farm planner, including new saved planning reports.
This does not mean any crop model passed scientific acceptance.

- Public API: `predictionsEnabled: true`, `state: unvalidated_enabled`,
  `scientificallyValidated: false`, `estimatedInputsAllowed: true`.
- Farm capability: `productionPredictionsEnabled: true` denotes operational
  enablement, not scientific approval or an already-published deployment.
- Every model result still has `productionAccepted: false`, failed-validation
  warnings and its original MAE/R² and baseline comparisons.
- The five existing genuine pipelines were reused, not retrained. No final-test
  prediction/scoring or validation-gate change was performed.
- Access is enabled for all app users, but farm ownership checks remain mandatory.
  No publication was performed or authorized.

## Inputs: what is actual and what is estimated

NASA POWER/MERRA2 climate must still be authentic, complete **2001–2020**
features at the containing five-arc-minute label-cell center. Missing climate
is not fabricated, replaced by 2019–2025 dashboard data or filled with zeros.

The original strict native SoilGrids preparation still requires at least **95%**
usable area per layer and retains the original units, native NoData masks and
0–5 cm depth. These original research/training requirements are unchanged.

With the visible **Allow estimated soil inputs** option enabled:

1. Try the original complete-input preparation.
2. If soil is incomplete, try means of available native pixels in the **same**
   label cell, requiring at least **10% per layer**. This is an operational
   estimate, not a newly validated source-coverage threshold. Missing parts
   may have substantially different soils.
3. If those means cannot be prepared, use the geographically nearest **recorded
   training cell's** original native soil means. Its coordinates, cell identity,
   distance, source evidence and dataset hash are disclosed. It is not claimed
   to be the nearest valid SoilGrids pixel worldwide or a validated similar
   agricultural region. No crop target, validation score or final-test cell
   participates in selecting this proxy.
4. Validate numerical ranges/units and texture consistency before inference.
   If no verified estimate can be prepared, withhold output rather than invent it.

Estimated jobs explicitly record `inputQuality: estimated_soil`,
`inputSummary.estimatedInputs: true` and original-contract `compatible: false`,
even though `estimatorExecuted: true`. Their source may be very distant.
Unchecking the option preserves the original missing-input refusals.

## Genuine operational checks

These are **maize model operational checks**, not accuracy/acceptance tests.
Values are a modeled suitability **0–10,000 index**, not probabilities,
percentages, yield, profit or whole-rotation scores.

| Location | Actual model index | Soil estimate used |
|---|---:|---|
| Irbid | 995.933164021164 | Available native pixels in the same source cell |
| Al Ain | 67.35587037037037 | Recorded training-source cell, **350.419 km away** |
| Colusa | 2921.3837515077507 | Available native pixels in the same source cell |
| Stuttgart | 3299.012846745846 | Available native pixels in the same source cell |
| Córdoba | 916.322947089947 | Available native pixels in the same source cell |

All five used actual required-period climate, executed the actual estimator
and retained original-contract mismatch and failed-validation disclosures.
Complete-input controls and all five crop pipelines were already verified in
the earlier delivery; no repeated training/download campaign was needed.

## Planner and saved-report behavior

1. Select a supported crop, review the estimated-input option, acknowledge failed
   validation and run the model. Repeat for additional desired crops.
2. Wait for completion, then generate a normal planning report below.
3. The backend captures latest same-owner/same-farm/unchanged-coordinate jobs
   from the current input-policy version as immutable `mlPredictions`.
   Matching crop candidates also receive their actual `modelEstimates`.
4. Warnings, source distance/coverage, original compatibility, exact raw output,
   estimator/version/dataset/artifact identities and timestamps are saved.
5. Later live jobs or cache pruning do not rewrite the saved snapshot.
   Older reports are not backfilled or retroactively changed.

Agricultural reference rules still determine the three rotation alternatives.
The model approximates single-crop historical suitability; it was not trained
to predict rotation effects, farm success, management benefit or causal outcomes.
The UI rounds the primary display to two decimals, with the exact raw value
available in a disclosure, including on narrow screens.

## Verification and limitations

- Full backend regression suite: **228 passed**.
- TypeScript/code-generated libraries: passed.
- Additional focused checks cover proxy training-membership, source checksums,
  missing-climate refusal, strict opt-out, partial-coverage disclosure, zero
  outputs, immutable snapshots and cross-workspace exclusion.
- Actual five-site evidence:
  `generated-artifacts/experimental-ml/estimated-checks/results.json`.
- Real browser journey passed on isolated test farm 232 and new report 96:
  an actual POST ran MZE with estimated inputs, returned
  **67.35587037037037**, and the normal report POST saved the same job,
  value, warnings, 350.4 km proxy distance and original-contract mismatch.
  The maize candidate received the same estimate. All three reference-based
  rotation scenarios remained present.
- Reload issued no ML POST and retrieved the unchanged saved snapshot.
  Another browser workspace received 404 for farm, prediction and report.
  No page/console errors occurred. At 402×874, document width was 387/387
  and the rounded number and provenance were contained.
- The exact raw value was verified in the API/saved payload and is rendered
  in a disclosure; the tester did not open that specific disclosure.
- Minor punctuation and nested reference-record wrapping defects found
  during the pass were corrected without changing model/report behavior.
  Focused backend checks: 13 passed after removing obsolete unavailable-model
  warnings from newly generated reports.

The existing reference planner can still display legacy `PROXY_DEMO_ONLY`
soil context, explicitly marked ineligible as ground truth. It is separate
from these model inputs; no demo-only soil constants were used in this ML path.

Important: operational enablement is **not** scientific acceptance. Sparse
geographic support, poor accuracy and substituted soil inputs remain real
limitations. None of these outputs should be used for real farming decisions.

The model bundles and research caches are currently local, ignored workspace
artifacts. A future publish/handoff must provision verified runtime artifacts
and the required proxy-source cache; merely merging source code does not
transfer those files. This work did not publish or claim that deployment
prerequisite was solved.
