# Phase 5 Stage A — implementation and review report

## A. Status and isolation

**Stage A is implemented for review. Stage B was not executed. Full Phase 5
is not complete.** No genuine, accepted model is available for live use.
The merged Phase 4 evidence reports `rejected_on_validation`, no deployable
model saved, no final holdout evaluation and no supported predictive coverage.
Candidate fitting is not proof of reliable farm advice.

Changes are on branch `phase5-stage-a`, in the separate worktree
`.local/phase5-stage-a`. They are **not applied to main or the current preview**.
No Phase 4 training files, Phase 3 agricultural rules, database schema,
deployment configuration or model activation settings were changed.
No migrations were run. Existing farm records were not edited.

Tests use rollback-isolated database transactions; PostgreSQL sequences may
advance during test inserts even though test rows are rolled back.

## B. Existing application audit and additions

| Area | Before this work | Stage A change |
|---|---|---|
| Map, farm profiles, navigation | Existing global selection, search/boundary/profile UI | Preserved; no redesign |
| New-coordinate NASA retrieval | Actual server requests, exact-coordinate cache, retries, UTC, validation, DB advisory lock, concurrency/rate limits and ingestion audits already existed | Repair partial-cache completeness checks; request only incomplete parameter groups; add retrieval-state metadata and malformed-response rejection |
| Four study regions | Stored NASA data and comparison summaries | Regression-tested as their own cached coordinates, without NASA downloads or inferred model coverage |
| Soil | Farmer measurements and exact-reference lookup of existing nearby SoilGrids proxies | Preserve provenance and refusal to substitute other study cities; new-location soil remains explicitly unavailable when not stored |
| Agricultural rules | 13 reference crops; baseline plus two conditional rotations when evidence permits | Engine unchanged; attach separate analysis evidence after the existing report is built |
| Model research | Genuine fitted candidates rejected on validation | Read actual committed JSON metadata; expose honest readiness, never load or activate a pickle |
| Farm history and priorities | Structured previous/current rotation in saved report input; profile history also exists as free text | Preserve both separately; no invented parsing. Current UI supports one selected priority, not multiple |
| Report persistence | Existing owner-scoped JSON result snapshots | Add optional `aiIntegration` snapshot without migrations; old reports remain readable |
| Privacy and request cost | Existing ownership and NASA concurrency controls | Six report generations/minute/browser owner; bounded evidence cache; redact requested API coordinates from the public ingestion-status listing |

## C. NASA and new-location behavior

The existing service uses official NASA POWER daily point requests with
`time-standard=UTC`, 2019-01-01 through 2025-12-31. It requests climate and
modeled wetness separately, keeps fill values missing, validates source units
and physical ranges, preserves returned geometry and original URL, and stores
observations for reuse.

Before this repair, a non-empty cache could qualify as fresh even with missing
parameters/dates. Stage A now counts each parameter's dates within the reference
period before treating coverage as complete. An explicit NASA fill counts as a
known source date but **not a valid measurement**; repeatedly downloading an
immutable fill would not make it evidence. Partial cache errors use the existing
three-minute cooldown, then retry incomplete groups. Complete historical groups
are not unnecessarily downloaded again. Existing conflicting observations are
not overwritten.

The service retains two attempts with backoff, 25-second HTTP request timeout
(8-second connection timeout), two concurrent retrieval slots and 12 new-location
retrieval admissions/minute/process. A database advisory lock prevents concurrent
retrievals of the same exact point across API workers. A second caller can receive
409 and retry rather than starting the same work. Cached/source failure states
are returned without fabricating weather.

### Real Córdoba check

On 2026-11-15, two actual requests to NASA at **37.8882, -4.7794** returned:

- 12,785 valid climate parameter values (five parameters × 2,557 days).
- 5,114 valid GWETTOP/GWETROOT values (two parameters × 2,557 days).
- 2019-01-01 through 2025-12-31, explicitly UTC.
- Returned source geometry rounded to longitude -4.779, latitude 37.888;
  the requested coordinates were retained unchanged.
- No parser warnings and no study-city substitution.

This was a real upstream request/parser check, not a simulated prediction or
a persisted farm. Its selected metadata and response hashes are in
`cordoba-live-check.json`. No live-test observations were written to the app's
database. Automated database tests separately verify the no-substitution failure
path using clearly identified synthetic failures.

### Operational limits

- Cache identity remains exact requested coordinates rounded to five decimals.
  No guessed NASA cell index is used. **Cross-point, same-grid-cell reuse is not
  implemented**; a reviewed source-grid mapping is needed before adding that
  optimization. This is not a worldwide bulk-download service.
- Rate/concurrency admission and the evidence cache are process-local. Multiworker
  shared admission limits remain a deployment-hardening step; exact-point DB
  locking already spans workers.
- NASA timeouts bound each outbound attempt, not the entire multi-group
  analysis. Existing loading/error states remain important for slow requests.
- Imported climate CSVs with unspecified time standards remain labeled as such;
  they are not silently aligned day-by-day with UTC live records.
- POWER is gridded environmental estimation, not a high-resolution sensor on a
  farm. No boundary-wide spatial aggregation is claimed.

## D. Versioned inference and feature contract

New public health endpoint: `GET /api/analysis/model-status`.
Its contract is `field-shift-analysis-1`; the active implementation stage is
`stage_a`. It exposes no model paths, private farm inputs or artifact downloads.

Readiness distinguishes not installed, incompatible, insufficiently validated
and temporarily unavailable. The wire contract reserves `validated_ready` for
a reviewed Stage B implementation. Stage A **cannot emit ready or enable
predictions**, even if an accepted research JSON report later appears.

Only application-controlled JSON files under `docs/phase4/evidence` are read.
The reader caches metadata until restart and returns copies, so callers cannot
mutate cached state. Malformed/missing metadata produces an explicit refusal.
No `joblib.load`, arbitrary model path, uploaded pickle, model upload route or
client-asserted verified feature vector was introduced.

The actual delivered Phase 4 schema is read from its metadata, not guessed:

- schema `gaez-approximation-1`, NASA POWER 2001–2020 monthly climate features;
- ISRIC SoilGrids area-mean 0–5 cm soil over the exact GAEZ cell;
- GAEZ-cell-center point climate, UTC, exact source/unit/spatial semantics;
- crop identities WHE, BRL, MZE, RCD, RCW, LRLM management scenario;
- target: approximation of a FAO/IIASA GAEZ modeled index, **not yield, profit,
  rotation benefit or weather forecast**.

`analysis.features.prepare_features` normalizes the server's real planner
evidence, soil source/depth, farmer profile, structured planning input,
coordinates, reference period, environmental provenance and retrieval state.
Its output is explicitly **not a compatible ML vector**. Current live planner
features are 2019–2025 point data and may include farmer assertions or nearby
proxies. They cannot be relabeled as the aligned research features. All model
features remain unavailable rather than zero-filled.

`aligned_climate_features` provides an internal/offline adapter to Phase 4's
existing, exact `power_features` transform, gated by the delivered contract.
It does not download, train, infer or prove spatial alignment. It avoids
reimplementing model preprocessing. Automatic 2001–2020 acquisition and native
soil aggregation for live farms remain disabled until the reviewed Stage B
pipeline and accepted model exist.

Prepared evidence is reused in a five-minute, 64-entry process cache. Its
content hash includes farm ID/profile, planning inputs, environmental/soil
snapshot and contract. Any of those changing invalidates reuse. Results are
copied before returning. There is no prediction-value cache.

## E. Coverage and refusal infrastructure

Each considered crop receives a coverage diagnostic. Stage A currently emits
only **INSUFFICIENT EVIDENCE**, with reasons, availability false and **no numeric
prediction or confidence**.

Checks expose missing/ineligible model evidence, crop identity ambiguity,
reference-period mismatch, missing soil, unverified/mixed time standards,
unsupported management/source/spatial semantics and incomplete environmental
data. Rainfed alone does not prove low-input LRLM management. Generic rice is
not silently mapped to either dryland or wetland rice. Explicit wheat/barley/
maize mappings are separate from reference crop names.

There is no invented similarity threshold or nearest-city confidence.
Supported prediction and similar-region estimate are reserved, disabled
behaviors. Phase 4's existing conservative range/distance/geographic screens
are documented interfaces, **not independently calibrated worldwide coverage**.
This work neither weakens them nor enables rejected candidates.

## F. Agricultural integration and separation

`POST /api/farms/{id}/plans` remains the report workflow. Its input, ownership
validation, history and existing agricultural report remain in place.

1. Validate the request and selected farm owner.
2. Bound repeated report work.
3. Retrieve/cache the selected coordinates' environmental data.
4. Reuse the existing source-aware soil/feature builder.
5. Invoke the **unchanged Phase 3 engine** and existing farmer drafts.
6. Attach separate Stage A model-readiness, source-compatibility and per-crop
   refusal evidence.
7. Save the whole snapshot in the existing JSON result field.

No suitability output is passed to Phase 3 today. `plannerUse` states that no
model evidence ranked or changed a rotation. Stage B must add a separately
reviewed evidence channel if supported predictions become available; it must
not replace agricultural rules or reinterpret suitability as rotation benefit.

Local planting calendars, seasonal water balance, cultivar constraints and
agronomist review remain Phase 3 scientific gaps, not hidden AI functionality.
The current planner preserves hypothetical date/reference-duration limitations.

## G. Farmer-facing behavior

The isolated UI adds a small availability panel to the existing saved-report
area, not a new dashboard or navigation system.

- Live availability check with loading, retry and source-error states.
- Clear unavailable-prediction wording, with no scores.
- New reports save a separate evidence panel and explain why predictions were
  withheld, with per-crop insufficient-evidence status.
- Old reports remain usable without the optional field.
- Reopened reports retain their historical evidence; the live panel separately
  shows current readiness.
- Existing environmental dashboard, source citations, farm editing, history
  form, rotation alternatives and report saving remain.

Actual loading and saved-snapshot markup was server-rendered in a component check;
this is **not an interactive browser
journey**. Typechecks and API integration tests passed. Because these changes
are intentionally not mounted in the main preview, no claim is made that the
isolated UI has been clicked through in the shared browser.

## H. Verification

- Full isolated Python regression suite: **149 tests passed**, including
  29 Stage A tests and the existing 40 Phase 4 software tests.
- After the final coordinate-redaction change, all **29 Stage A tests passed**
  again, including public status redaction.
- OpenAPI code generation and full workspace TypeScript checks passed.
- UI server-render checks passed for actual Stage A evidence and loading state.
- Actual Córdoba NASA requests returned all seven variables, as above.
- Four stored study locations were tested with upstream downloads forbidden.
- Different crops, soil pH, irrigation and priorities at the same location
  changed reference reports; model predictions remained unavailable in both.
- Tests cover ownership, saved snapshot reopening, malformed metadata, no
  deserialization, cache mutation/invalidation, malformed NASA payloads, invalid
  input, request limits, unavailable soil and no silent history parsing.

The first isolated full run had two import-test failures because ignored
uploaded ZIP files are not copied by Git worktrees. Providing a read-only link
to the existing original upload fixed this test setup issue. No importer
behavior was relaxed, original file overwritten, or user data deleted.
One existing Starlette/httpx deprecation warning remains; it is not a failure.

Software tests are not evidence of agronomic model accuracy. Any synthetic
accepted-model success path in the existing Phase 4 tests is a temporary
software fixture, never a farmer prediction.

## I. Exact Stage B dependencies

Phase 4 must supply an **accepted** artifact and independently reviewable
evidence, not merely fitted candidates:

1. Trusted model plus preprocessing pipeline, integrity hashes and approved
   application-controlled loading location.
2. Exact feature schema, units, source versions, spatial semantics, period,
   soil depth/statistic and validated missing-data policy.
3. Target meaning/scale and crop/management coverage.
4. Runtime compatibility versions and reproducible genuine reference outputs.
5. Predeclared geographic validation and untouched-holdout acceptance results,
   regional/crop error evidence and limitations.
6. Defensible numeric ranges, multivariate support method and independently
   reviewed coverage/reliability thresholds. Similar-region estimates need
   separate supporting validation; proximity alone is insufficient.
7. Review of any future inference adapter and safe failure behavior before
   activation.

This work does not retrain Phase 4, evaluate its final holdout, install new
models or fabricate a reference prediction.

## J. Safe integration instructions

Review branch `phase5-stage-a` against main before applying it. Read its source,
test results and this report. It contains **no schema migration, dependency
version change, shared production config change or automatic activation**.

After explicit approval, apply/review the branch normally, run the codegen and
checks below, restart existing API/frontend workflows once and verify the UI.
Do not run migrations for this change. Do not pass arbitrary paths to a
joblib loader or expose trusted-model files to users.

```sh
pnpm --filter @workspace/api-spec run codegen
pnpm run typecheck
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=artifacts/api-server \
  uv run --no-sync python -B -m unittest discover -s artifacts/api-server/tests -v
```

Import regression tests require the original uploaded
`attached_assets/Field_Shift_Replit_Data_1794680523930.zip`. It is intentionally
not added to this branch or copied into Git. In a separate worktree, provide
read-only access to that existing upload before testing.

Do not cherry-pick Phase 5 as proof Phase 4 passed. The correct post-merge
readiness remains insufficiently validated, with predictions disabled.

## K. Ordered remaining work before full Phase 5

1. Review this isolated Stage A branch and run a browser regression after
   approved integration; verify maps, farm create/edit, soil and report flows.
2. Complete Phase 4 scientific acceptance without weakening its gates or
   consuming the reserved holdout for iterative tuning.
3. Implement/review model-aligned live source acquisition and source-aware
   feature preparation, including native SoilGrids aggregation and complete
   2001–2020 features; never silently switch farmer data or periods.
4. Review trust/integrity and safely load the accepted pipeline; reproduce
   real reference predictions and validate preprocessing/units.
5. Calibrate/review coverage and refusal behavior for supported conditions and
   previously unseen regions; keep similar-region estimates disabled unless
   separately justified.
6. Pass only supported model evidence to a reviewed Phase 3 adapter, preserve
   source labels and test farmer-facing comparisons.
7. Add shared multiworker request admission and verified same-grid cache reuse
   if needed for scale.
8. Complete local calendars and crop-season water accounting in their separate
   agricultural work; they are not generated by suitability inference.
9. Run end-to-end supported/refused/offline/security/browser tests and obtain
   scientific/operator review before enabling a Stage B workflow.

## Authoritative source references checked for this work

- NASA POWER Daily API, UTC/LST, request limits and point semantics:
  https://power.larc.nasa.gov/docs/services/api/temporal/daily/
- ISRIC SoilGrids native WebDAV/VRT access:
  https://docs.isric.org/globaldata/soilgrids/WebDav.html
- Existing agricultural citations remain in the unchanged reference library.
- Actual model requirements and validation outcome:
  `docs/phase4/ADAPTER.md`, `MODEL_CARD.md`, `evidence/feature-contract.json`,
  `evidence/run-summary.json`, `evidence/evaluation.md`.
