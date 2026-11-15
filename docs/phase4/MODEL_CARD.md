# Model card: GAEZ suitability approximation foundation

## Release status

**Genuine supervised candidates were trained and rejected on geographic
validation. No deployable model is included or activated; Phase 4 scientific
validation is not complete.** Inspect `evidence/run-summary.json` and
`evidence/evaluation.md`. Actual model fitting is not proof of useful accuracy.

## Intended target and use

Approximate the FAO/IIASA **GAEZ v5 RES05-SXX all-land suitability index**,
0–10,000 index units, for historical 2001–2020, AgERA5, rain-fed/low-input
management. The index is a modeled land assessment, **not** a probability of
crop success or an observed harvest outcome.

The only verified layer equivalents are Wheat (WHE), Barley (BRL), Maize (MZE),
Dryland rice (RCD) and Wetland rice (RCW). This is five source crop types
covering the four requested crop families; generic rice remains unsupported.
Verified source-layer coverage is distinct from validated predictive coverage.
**Current predictive coverage is empty.**

Not for observed yield, profit, soil-health improvement, rotation benefit,
irrigation prescriptions, planting-date decisions, current-year forecasts,
insurance, lending, or autonomous farm-management decisions.

## Evidence and sampling

The task retrieved authentic five-arc-minute GAEZ rasters and sampled 180
geographically distributed cells (900 crop/cell labels). The sample retains
zero suitability and non-cropland; it is not a cropland-only or globally
representative probability sample. Per-cell POWER historical climate and
masked native SoilGrids subsets are processed independently.

The four original 2019–2025 demonstration locations are an ingestion audit,
not the training dataset. Their proxy soil data are excluded.
See `SOURCES.md`, `evidence/source-audit.json`, and the run's quality report.

The initial pilot retained 95 eligible cells / 475 rows and failed readiness.
A target-independent preregistered geographic supplement retained
**124 eligible cells / 620 rows** in total, with **74/24/26**
train/validation/test cells. Readiness passed without changing thresholds.
Dummy/crop-mean baselines and four Ridge/Random Forest configurations were
genuinely fitted. The best Random Forest's validation MAE **1,672.801** exceeded
the **1,500** gate (RMSE 2,535.843, R² 0.057; dummy MAE 1,717.194).
**The candidate was rejected before final-test evaluation or model saving.**

## Inputs and preprocessing

Version: `gaez-approximation-1`. The contract saves names, order, units,
2001–2020/UTC interpretation, exact 0–5 cm soil depth, aggregation, categorical
codes and strict complete-input policy.

Twenty-four numeric climate features (12 monthly mean temperatures and 12
mean monthly rainfall totals), five numeric modeled topsoil properties,
crop and scenario. Coordinates are used for scientific matching/partitioning,
not as predictors. StandardScaler and exact OneHotEncoder are stored with
the estimator only when accepted. No label-derived input, farmer request,
synthetic target, imputed soil value or undocumented crop substitution is
permitted.

## Evaluation design and gates

Predeclared in `backend/machine_learning/config.json`; rationale and exact
commands in `REPRODUCE.md`. Seeded 10° partitions, a 150 km buffer and
conservative overlapping meteorological-footprint purging separate
train/validation/test. Repeated crops share their geographic assignment.
Training-only CV is also buffered. Candidate selection uses validation only;
the final test is reserved once per dataset hash and never used for tuning.

Dummy and crop-mean baselines, Ridge and Random Forest candidates are available.
Promotion requires meaningful baseline improvement, bounded aggregate,
per-crop and per-region error, and adequate independent geographic support.
Readiness blocks fitting when the real dataset is inadequate.

**No agricultural accuracy metric is asserted merely from software tests.**
The test-only accepted serialization fixture is temporary and synthetic.
It is never shipped, activated, or counted as a genuine trained model.

## Limitations and known risks

* GAEZ assessments themselves have modeling assumptions and uncertainty.
* POWER MERRA-2 climate and GAEZ AgERA5 climate differ even in matching years.
* Regional weather and ~10 km label cells do not resolve individual fields.
* Static modeled 0–5 cm soil can omit relevant root-zone properties and change.
* Native pixel-center aggregation approximates boundary overlap.
* Soil masking excludes desert, urban, water and other areas and may create
  geographic selection bias. Exclusions do not mean a crop is unsuitable.
* The pilot does not establish climatic-zone representativeness, global
  coverage, fairness, temporal transfer, or farm-outcome utility.
* Temperature/rainfall alone omit humidity, radiation, extremes, terrain and
  many processes represented inside GAEZ. Compact features may not approximate
  GAEZ well; more capacity is not a substitute for independent evaluation.
* Future accepted-model support checks combine ranges, joint environmental
  distance and tested geography. They are not a validated full Phase 5 system.
* Pickled artifacts require trusted operator control; file hashes are not
  cryptographic proof of publisher identity.

## Operational and integration constraints

No HTTP endpoint or model registry activation, database migration, production
write, frontend change or planner modification was added. The existing
reference-based planner remains the application behavior.

The standalone predictor rejects missing/incompatible/rejected models,
unsupported inputs and insufficient evidence without scores or confidence
percentages. `ADAPTER.md` defines future integration without reinterpreting
the existing 2019–2025 environmental feature builder.

## What is required before release

Enough replay-verified aligned cells and effective coarse environments,
untouched geographically adequate evaluation, all declared acceptance gates,
scientific review of source alignment and support limits, and explicit
operator approval of a trusted accepted artifact. Live integration and
publication are separate future work, not enabled by completing this task.
