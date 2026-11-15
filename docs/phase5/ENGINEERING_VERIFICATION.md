# Field Shift — Stage A integration and engineering verification

Verified on **2026-11-15**. **Stage A is integrated into development `main`.
Stage B remains disabled.** This report supersedes the earlier isolated
implementation report. No production publish, deployment configuration change,
schema migration, real model training or activation was performed.

## A. Independent review and safe integration

### Repository check

- Active branch before integration: `main`, clean.
- The supplied `.local/phase5-stage-a` directory was verified using
  `git worktree list`: it was an actual separate Git worktree on
  `phase5-stage-a`, with its implementation committed and recoverable.
- Main had only an intervening asset-metadata change relative to the common
  base. There were no overlapping application edits or uncommitted changes.
- The Stage A branch was merged normally with a merge commit, preserving
  main's asset metadata. No conflicts, force reset or force push occurred.
- The Phase 3 agricultural engine, Phase 4 machine-learning directory,
  dependency versions and deployment configuration were unchanged.

### Independent review findings and corrections

The independent code reviewer initially recommended **holding integration**.
All three actionable findings were addressed before merging:

| Finding | Correction | Regression evidence |
|---|---|---|
| Counts across products could hide missing NASA dates | Count distinct dates for the expected `POWER_DAILY` product and NASA POWER source, rather than total rows | Thousands of alternate-product rows on one date cannot make the NASA cache complete |
| Location-level UTC stamp could mislabel mixed imported/live data | Rename it to `requestTimeStandard`; preserve each observation's original time standard | Mixed imported unspecified-time and live UTC records retain their distinct provenance and warnings |
| Cookie renewal and multiple workers could bypass process-local budgets | Add shared PostgreSQL admission accounting under transaction advisory locks | Per-owner and global limits, owner rotation, private admission rows and technical-row expiry tested |

The shared admission ledger reuses the existing ingestion-report table with a
private reserved source prefix. It requires **no migration**. Only these new
technical entries expire after 24 hours; environmental values, real ingestion
audits and farmer records are not deleted. Public status endpoints exclude the
technical entries entirely.

Current budgets:

- Six report admissions/minute per browser owner.
- Twenty-four report admissions/minute globally, independent of cookie changes.
- Twelve uncached environmental retrieval admissions/minute globally.
- The existing exact-point PostgreSQL lock still prevents duplicate concurrent
  source work. Admission commits occur before that retrieval lock.
- Existing per-process two-request retrieval slots remain an additional bound.

Counters are shared via PostgreSQL, not a worker-local dictionary. Tests exercise
the database-backed accounting and owner-rotation behavior. A distributed load
or saturation benchmark was not performed.

## B. Fresh automated and frontend results

These checks were actually executed after the review corrections; they are not
copied from the earlier Stage A report.

| Check | Result |
|---|---|
| Full Python discovery suite | **153 passed, 0 failed** |
| Stage A subset | **33 passed**; included in the full suite |
| TypeScript workspace check | Passed across libraries, API, Field Shift, sandbox and scripts |
| Generated OpenAPI clients and Zod types | Regenerated successfully; no conflicting route/schema introduced |
| Frontend retry unit tests | **3 passed, 0 failed** |
| Frontend status component server-render checks | **3 passed:** saved snapshot, loading, error/retry |
| Browser farmer journey | Passed with actual NASA data and persisted farm/report |
| Focused browser retry verification | Passed after two synthetic transport-only 409s, then real cached data |
| Whitespace/diff check | Passed |

The final retry-helper change was followed by the Field Shift TypeScript check.
The only subsequent status-component edit added missing text spacing.

Commands:

```sh
pnpm --filter @workspace/api-spec run codegen
pnpm run typecheck
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=artifacts/api-server \
  uv run --no-sync python -B -m unittest discover -s artifacts/api-server/tests -v
node --experimental-strip-types --test \
  artifacts/field-shift/src/lib/environment-retry.test.ts
pnpm --filter @workspace/field-shift run typecheck
```

The component checks bundled the actual `AnalysisStatus` component, wrapped it in
a React Query provider and server-rendered it with explicit software fixtures.
The first attempt to seed an error state was automatically treated as a new
query attempt by React Query. Disabling retry-on-mount in that **test fixture**
made the error/retry assertion deterministic; no application workaround was
added for this test-harness issue.

The existing Starlette/httpx deprecation warning remains non-blocking.
Phase 4 software tests may fit temporary synthetic estimators as test fixtures;
the real scientific training dataset and reserved holdout were not used.

## C. Actual Córdoba retrieval, persistence and cache reuse

Primary reference point: **37.8882, -4.7794**, Córdoba, Spain. This is a synthetic
farm test at a city reference point, not a verified farm or soil survey.

Before the browser journey there were **zero** stored environmental values for
the exact location key `37.88820,-4.77940`.

Normal browser dashboard requests caused the application's NASA service to:

1. Accept and retain the selected coordinates.
2. Check its exact-coordinate cache.
3. Request missing daily climate and wetness parameters from official NASA POWER.
4. Validate response units, dates, fills and explicit UTC metadata.
5. Store genuine observations and source metadata in development PostgreSQL.
6. Generate the existing history, monthly, seasonal and annual summaries.
7. Display the data in the farm dashboard.

Stored coverage:

| Parameter | Rows | Non-missing values | Distinct dates |
|---|---:|---:|---:|
| T2M | 2,557 | 2,557 | 2,557 |
| T2M_MAX | 2,557 | 2,557 | 2,557 |
| T2M_MIN | 2,557 | 2,557 | 2,557 |
| PRECTOTCORR | 2,557 | 2,557 | 2,557 |
| RH2M | 2,557 | 2,557 | 2,557 |
| GWETTOP | 2,557 | 2,557 | 2,557 |
| GWETROOT | 2,557 | 2,557 | 2,557 |
| **Total** | **17,899** | **17,899** | **2,557 per parameter** |

The reference period is **2019-01-01 through 2025-12-31**, explicitly UTC.
The summary location has `studyId: null`, the selected Córdoba coordinates and
the exact-coordinate matching policy. No demonstration-city data were substituted.

A subsequent request returned:

```json
{
  "mode": "cached",
  "requestMade": false,
  "coverageComplete": true
}
```

The before/after environmental row count remained **17,899**, the location's
last-attempt timestamp was unchanged and its NASA ingestion-audit count remained
**one**. The repeated request neither downloaded nor inserted another dataset.
The source URLs, parameter metadata, returned geometry and retrieval timestamps
are retained with the observations.

The four original study locations were also regression-tested with upstream
requests forbidden: their own complete caches were reused.

### First-load contention and its correction

The genuine first-load browser run initially encountered 409 responses in the
summary and wetness panels because parallel panels requested the same uncached
point. Manual bounded retries recovered genuine data; this was recorded, not
presented as an error-free initial load.

The environmental UI now treats 409 as bounded in-progress waiting:
up to six automatic retries with 2, 4, 8, 16, 20 and 20 second waits.
It does not automatically hammer 429, validation or authorization failures.
Ordinary network/server failures retain one retry.

A focused follow-up in the **same testing browser** intercepted just the first
two summary responses with software-fixture HTTP 409s, then allowed the real
cached server response. The panel stayed loading, did not show the unavailable
screen, and recovered without any Retry click. Observed request times were about
0.8, 2.8 and 6.9 seconds, with available Córdoba data visible at 8.7 seconds.
No farm writes, NASA downloads or fake weather data were involved in that check.
The retry cap and no-retry 4xx behavior were unit-tested, not browser-load-tested.

## D. Actual farmer browser journey

Test record retained for verification:

- Farm **102**, `Córdoba Test Farm 4mino`.
- Report **50**.
- Synthetic profile: 12 hectares, current crop Wheat, limited irrigation,
  conserve-water priority, soil type entered as Unknown, soil pH/moisture left
  blank.

### Browser interactions verified

1. Opened the global map, entered the exact Córdoba latitude/longitude and placed
   the pin. The map and selected coordinate text matched.
2. Continued to farm creation, filled the synthetic profile and saved it.
   The API returned 201 and the overview showed the correct location/profile.
3. Loaded real environmental charts and source limitations. The UI showed
   gridded estimates, 84 months and seven years.
4. Checked soil availability: **no soil estimate for this location**, with
   unavailable properties rather than another city's demo proxy.
5. Opened the existing Rotation planner. Entered structured previous crops
   **Wheat, Chickpea**, oldest first, and hypothetical planting date 2027-02-01.
   Seasonal water was left blank because no actual budget was supplied.
6. Generated and saved the reference-based report, with the farmer baseline
   and two distinct alternative scenarios.
7. Expanded the AI-availability explanation: predictions unavailable, rejected
   validation, missing accepted model, period mismatch and missing/incompatible
   soil/management inputs were visible. No ML score/confidence was shown.
8. Reloaded and reopened the saved report from history.
9. Edited only this synthetic farm's water-constraints note, saved and reloaded.
   Coordinates, crop history and other profile inputs persisted.

### Browser-context API assertions

The same browser's request context confirmed:

- Farm 102 retained `farmSize: 12`, `irrigation: limited`,
  `goal: conserve_water` and the selected coordinates.
- Report 50 retained `inputs.planning.previousCrops: ["Wheat","Chickpea"]`,
  `currentRotation: ["Wheat"]` and the entered date.
- The report had three scenarios, predictions disabled and feature
  compatibility false, with explicit reasons.
- A separate clean browser workspace received **404** for both the farm and its
  saved report.

### Authentication limitation

There is **no account-login flow** in the existing application. Identity is a
signed anonymous browser-workspace session cookie. The normal session flow,
reload persistence and cross-workspace ownership checks were tested. Email,
password, OAuth login and cross-device account recovery cannot be claimed as
tested or implemented.

The synthetic farm/report remain in the tester's browser workspace. A different
browser workspace—including the creator's current session—will not automatically
have permission to open those private records. Their IDs are evidence, not a
promise of public access.

### Screenshot evidence

The testing browser captured and inspected screenshots of:

- Córdoba pin and exact coordinates.
- Saved farm overview and environmental charts.
- Modeled wetness labeling and unavailable soil.
- Expanded model-refusal reasons.
- Profile after editing and final available dashboard.
- Automatic recovery after the two controlled 409 transport responses.

No page JavaScript exceptions occurred. First-run console resource errors were
the expected in-progress 409 responses; the focused retry fixture produced only
its two intentional 409 messages.

## E. Database preservation and security

Before testing, the original records were hashed without writing raw profiles
or owner cookies into the report. A final comparison found:

| Table | Before | After | Original rows missing or changed |
|---|---:|---:|---:|
| Farms | 4 | 5 | **0** |
| Environmental values | 89,495 | 107,394 | **0** |
| Environmental locations | 5 | 6 | **0** |
| Soil-property estimates | 4 | 4 | **0** |
| Recommendation results | 2 | 3 | **0** |

Additions were the explicitly authorized synthetic test farm/report and Córdoba
environmental data. Backend test data were rolled back. PostgreSQL sequences
can advance during rollback-isolated tests; that is not lost user data.

Verified controls:

- Farm and saved-report ownership checks deny another browser workspace.
- Public ingestion status redacts private API-request coordinates and excludes
  internal admission records. The reserved ledger contains hashes, not raw
  browser-owner identifiers.
- Coordinate bounds/non-finite values, unexpected planning fields, invalid
  priorities, invalid water amounts and malformed NASA payloads are rejected.
- Report admission and owner-rotation limits are enforced in the shared DB.
- Source cache completeness cannot be manufactured by alternate product rows.
- No public model-path/verified-feature upload interface or pickle loading was
  introduced. Accepted-looking research metadata cannot activate Stage A.
- No secrets, session cookies or test credentials were printed or committed.
- No production database access or migration was performed.

Evidence under `generated-artifacts/phase5-integration/` includes the fresh
backend log, component results, aggregate preservation comparison and Córdoba
cache verification. The directory is ignored by Git and deployment packaging.
The baseline file contains row digests, not raw private profiles.

## F. Agricultural integrity and model safety

The reference planner still applies selected-location NASA context, available
soil evidence, crop-family/history rules, irrigation/water constraints and the
selected priority. An earlier API comparison of two different farm-input sets
at the same location remains covered by the executed suite.

The browser's three scenarios are **reference-based, conditional comparisons**,
not ML-ranked crops or validated rotation outcomes. Source labels include USDA
NRCS rotation and FAO diversification references. No exact water savings,
profit, yield improvement or reliability percentage was fabricated.

Structured previous crops are saved in the report input and passed to Phase 3.
The free-text profile history is preserved separately and is **not silently
parsed into structured history**. Reopening a report retains its historical
input snapshot; editing the farm does not retroactively rewrite the old report.

Current model readiness:

- `stage: stage_a`.
- `state: insufficiently_validated`.
- `predictionsEnabled: false`.
- No accepted model loaded or rejected candidate used.
- Live farm evidence remains 2019–2025. It is explicitly incompatible with the
  model's 2001–2020 contract; no relabeling or zero-filled feature vector occurs.

The legacy Phase 3 report field still says `modelStatus: not_trained`, because
that unchanged engine has no trained predictor. The new readiness panel is the
accurate research-status explanation: candidates **were fitted**, failed
validation and are **not accepted or active**.

## G. Remaining dependencies before Stage B or production acceptance

1. **Phase 4 geographic validation:** improve authentic data coverage and
   justified model/features using training/validation only. Preserve the
   predeclared gates and reserved geographic holdout. Supply a genuinely
   accepted model with crop/regional evaluation and limitations.
2. **Aligned historical pipeline:** acquire the complete model-required
   2001–2020 NASA UTC period at the documented GAEZ-cell spatial support.
   Reuse the actual Phase 4 preprocessing contract. Preserve missing days,
   units, time standards, source versions and provenance; do not repurpose
   incompatible imported records by changing metadata.
3. **Model-aligned soil acquisition:** use documented native ISRIC methods,
   valid masks and area means over the exact GAEZ label cell, 0–5 cm, with
   source/statistic/unit semantics required by the model. Farmer claims and
   nearby `PROXY_DEMO_ONLY` samples cannot be substituted for those features.
4. **Calibrated coverage:** independently justify range, multivariate and
   geographic support checks with held-out evidence. Similar-region estimates
   remain disabled without separate validation. Proximity is not confidence.
5. **Genuine Stage B inference:** review a trusted model/preprocessing bundle,
   hashes, versions, provenance and acceptance results; reproduce genuine
   reference outputs; pass only supported outputs through a reviewed
   agricultural evidence adapter. Do not reinterpret suitability as yield or
   rotation benefit.
6. **Production acceptance:** perform separately authorized deployed-environment
   configuration checks, realistic load/rate tests, failure monitoring and
   scientific/operator review. If account-based use is required, authentication
   and recovery are a separate product requirement, not silently supplied here.

Additional known limits:

- Verified Córdoba retrieval does not establish data availability or reliable
  predictions for every worldwide coordinate.
- Cache reuse is exact-coordinate; verified cross-point grid-cell reuse is
  not yet implemented.
- Whole-farm polygon environmental aggregation is not implemented or claimed.
- No model-aligned automatic soil data were fabricated for Córdoba.
- Local crop calendars, crop-season water balance and agronomic review remain
  separate outstanding agricultural work.
- No harvest-yield prediction or weather forecasting was implemented.

## H. Final result

The requested Stage A review, correction, safe development integration,
real-data persistence/cache verification, browser farmer journey and fresh
automated checks are complete. Full Phase 5 inference is **not** complete:
the unvalidated-model boundary is intentionally enforced.

Official source documentation:

- https://power.larc.nasa.gov/docs/services/api/
- https://power.larc.nasa.gov/docs/services/api/temporal/daily/
- https://docs.isric.org/globaldata/soilgrids/WebDav.html

The existing reviewed Phase 4 contract and model card remain authoritative:
`docs/phase4/ADAPTER.md`, `MODEL_CARD.md` and the committed evaluation evidence.
