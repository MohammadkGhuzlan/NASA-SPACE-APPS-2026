# Phase 3: initial reference-based agricultural planning

## Implemented scope

This release starts Phase 3 without rebuilding the application or training a model.
The existing map, NASA services, farmer profiles and manual rotation drafts remain.

- Public reference library: Wheat, Barley, Grain maize, Dry bean, Pea and Potato.
- FAO generic sowing-to-last-harvest durations, total crop-water ranges and drought sensitivity.
- FAO diversification/soil-cover/minimum-disturbance principles.
- University of Minnesota Extension crop-group descriptors and explicitly region-scoped rotation cautions.
- Farmer-specified planned sequence, previous crops, exclusions, hypothetical sowing date,
  crop-available seasonal water estimate and operational limitations.
- Deterministic current/A/B scenario exploration with source-linked benefits and risks.
- Conditional harvest arithmetic and historical NASA monthly climate context.
- Versioned, immutable report snapshots stored in the existing recommendation-results table,
  with no model ID. Reports do not replace or modify manual drafts.
- Session-owner-scoped generation, history and reopening.

## Reference verification

Reviewed on 2026-11-15:

1. https://www.fao.org/4/s2022e/s2022e07.htm
   - Table 6 durations; Table 14 indicative total crop-water requirements and drought sensitivity.
   - The manual explicitly favors local information and warns that generic ranges are approximate.
2. https://www.fao.org/conservation-agriculture/en
3. https://www.fao.org/conservation-agriculture/in-practice/species-diversification/en/
4. https://extension.umn.edu/small-grains-crop-and-variety-selection/small-grain-crop-rotations
   - Minnesota/North Dakota evidence is not treated as worldwide validated advice.

Several crop-specific FAO landing pages returned “page not found”; no numeric fact
was taken from those failed fetches or search snippets. The accessible FAO manual
is the cited numeric source.

## Rules and their limits

- Exclude named crops using exact curated aliases, not substring guesses.
- Mark conflicts if a farmer's total crop-available water estimate falls below the
  generic FAO minimum; this is a conservative reference comparison, NOT a water balance.
- Water-priority exploration orders candidates by generic minimum water requirement.
  Soil-health exploration brings legumes first. Other priorities use stable name order.
  These are transparent exploration policies, not verified crop rankings.
- Form distinct three-crop exploratory sequences with a legume, without adjacent
  broad-group repetition and without a maize-to-wheat/barley transition.
- Apply regional disease cautions as review prompts, not local disease predictions.
- Preserve unknown crops in the current sequence and mark unassessed requirements.
- Do not parse unstructured history or equipment constraints into invented facts.
- If fewer compatible reference crops remain, withhold alternatives rather than invent them.
- Planting dates are user assumptions. Adding generic durations creates hypothetical
  harvest ranges, not locally validated sowing/harvesting windows.
- Later sequence dates assume immediate succession and carry duration uncertainty forward;
  actual seasonal gaps and turnaround remain unknown.
- Historical context uses equally weighted complete monthly aggregates for calendar
  months touched by the maximum duration. It is not a climate-suitability test or forecast.
- Multi-crop water totals span multiple crop cycles, not one season's irrigation demand.

## API and persistence

- `GET /api/knowledge`
- `GET /api/farms/{id}/plans`
- `POST /api/farms/{id}/plans`
- `GET /api/farms/{id}/plans/{planId}`

Reuses existing crop definitions, crop requirements, source registry and recommendation
results. No schema migration or production schema change is required. Startup performs
idempotent reference-data inserts; no destructive updates to user farm/draft records.

Reports preserve input/profile snapshots, NASA provenance, source-sensitive soil inputs,
library/engine versions, limitations and references. Browser-session ownership remains
the existing access mechanism; this release does not add accounts or recovery.

## Explicitly not complete

This is the initial, deliberately limited Phase 3 release, not a claim that all agricultural
planning knowledge has been curated:

- No globally verified local calendars, cultivar adaptation, crop-specific temperature,
  soil-pH, salinity, drainage, photoperiod or vernalization requirements.
- No automated interpretation of free-text operational constraints.
- No yield/economic/soil-health outcome estimates or quantified water savings.
- No supervised training, FAO GAEZ label dataset, suitability confidence or similar-region inference.
- No PDF export or downloadable generated report file; saved reports reopen in the app.
- Earlier Phase 2 dashboard gaps remain outside this release.

## Verification

Automated rule tests and rollback-isolated API tests cover reference values, aliases,
water conflicts, exclusions, missing data, harvest arithmetic, unknown crops, distinct
alternatives, provenance, immutable save/reopen, owner separation, draft preservation
and idempotent reference seeding. Run:

```sh
PYTHONPATH=artifacts/api-server uv run python -m unittest discover -s artifacts/api-server/tests -v
pnpm run typecheck
```

Delivery verification: all 75 existing and new Python tests passed, including 23
planning-specific tests. Root TypeScript checking passed. Browser checks confirmed
generation, saving, reload/reopening, visible invalid-exclusion errors without
extra records, unchanged farmer drafts, zero-water withheld alternatives, and the
six-crop reference library. A recursive provenance overflow was fixed and rechecked:
no horizontal overflow at 390px or 1280px, and the report button is reachable.
