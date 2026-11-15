# Preregistered geographic supplement

Declared November 15, 2026, **before any supervised fitting, validation error,
or final-test evaluation**. The initial 180-cell pilot retained 95 cells and
failed the unchanged 120-total / 20-test readiness floors. No model has been
trained and no final-test performance is known.

## Additional sampling

1. Keep all 180 original sampled cells and all their exclusions.
2. Draw an independent candidate pool with `sample_labels`, seed **43**,
   requested pool size **1200**. Use the same five verified source layers,
   period/scenario, latitude screen, valid-label mask, geographic strata and
   screening bins. Do not inspect target magnitudes to choose cells.
3. Exclude original cell IDs and candidate centers within 150 km of an already
   chosen source cell (also excluding conservative shared weather footprints).
   This spacing is target independent and reduces redundant environmental
   acquisition. Do not use soil masks to preselect apparently easy examples.
4. Select in deterministic candidate order, using the **unchanged** split
   seed 42 / 10° block hash assignment: **60 test**, **40 train** and
   **20 validation** source cells, total **120** additional cells.
5. Acquire the same complete 2001–2020 POWER and native masked 0–5 cm
   SoilGrids features. Retain the same ≥95% valid-area and complete-input
   rules. Failed cells remain explicit exclusions, not replacements.
6. Assemble the combined 300-cell / 1500-label planned dataset, then replay
   sources and apply the original buffered split/readiness procedure.

This targeted geographic allocation addresses the observed **sample-count**
shortfall, not model error. The resulting evaluation population is a
deliberately stratified all-land pilot, not an area-weighted global benchmark.
Do not compare its aggregate metrics to the initial pilot as an accuracy gain:
there were no initial pilot model metrics.

## Frozen model/evaluation rules

The existing `config.json`, feature contract, candidate set, preprocessing,
baseline comparisons, validation selection, once-only final holdout reservation
and promotion gates remain unchanged. In particular, low-support test regions
must still block promotion. A rejected model is reported honestly and is not
saved as a deployable estimator.

If this combined run still fails readiness, report that result. Further
sampling requires another documented protocol, never changed label values,
relaxed quality thresholds, or reuse of test performance for model selection.

## Reproduce

```sh
export PYTHONPATH=artifacts/api-server
uv run python -m backend.machine_learning supplement \
  --samples generated-artifacts/phase4/samples.json \
  --out generated-artifacts/phase4/supplemented-samples.json
uv run python -m backend.machine_learning prepare \
  --samples generated-artifacts/phase4/supplemented-samples.json \
  --cache generated-artifacts/phase4/environment \
  --out generated-artifacts/phase4/supplemented
uv run python -m backend.machine_learning train \
  --dataset generated-artifacts/phase4/supplemented/dataset.json \
  --out generated-artifacts/phase4/supplemented-training
```
