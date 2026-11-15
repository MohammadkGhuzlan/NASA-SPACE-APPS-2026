# Non-invasive Phase 3 adapter contract

No route, planner import, persistence hook or live activation was added.
The existing Phase 3 planner must continue reporting its reference-based status.

## Python interface

```python
from backend.machine_learning.contract import PredictionInput
from backend.machine_learning.inference import SuitabilityPredictor

# None is the correct configuration until a reviewed accepted bundle exists.
predictor = SuitabilityPredictor(directory=None)
result = predictor.predict(PredictionInput(
    latitude=32.541666666666664,
    longitude=35.875,
    features=aligned_features,
))
```

`aligned_features` must contain exactly the ordered numeric/categorical schema
in `backend.machine_learning.contract.CONTRACT`:

* `tmean_m01`…`tmean_m12`: 2001–2020 calendar-month mean daily temperature, C;
* `rain_m01`…`rain_m12`: mean of 20 annual calendar-month precipitation totals,
  mm/month;
* `clay_pct`, `sand_pct`, `silt_pct`, `ph`, `soc_g_kg`: native SoilGrids mean
  predictions aggregated over the exact GAEZ cell polygon, 0–5 cm;
* `crop`: `WHE`, `BRL`, `MZE`, `RCD`, or `RCW`;
* `scenario`: `LRLM` only.

The adapter caller must prove that features satisfy the source, depth,
aggregation and complete-period contract. Source-quality fields are assertions
at this interface, **not independent verification**. Do not expose a public
endpoint that accepts client-supplied “verified” status.

The existing `backend.environment.features.build_features` output is
**incompatible**: it uses 2019–2025 and may select farmer assertions or nearby
soil proxies. Do not relabel it, zero-fill it, or feed it directly to this model.
Do not use current farm weather as if it were a historical 20-year normal.
Map farmer crop names explicitly; generic rice requires a choice of dryland
or wetland rice, not automatic substitution. Irrigation categories such as
“limited” or “fully_irrigated” do not map to LRLM.

## Reproducible actual availability response

After preparation, choose any eligible record, or use the
`example-request.json` supplied alongside the final report when present:

```sh
PYTHONPATH=artifacts/api-server uv run python -m backend.machine_learning \
  predict --request docs/phase4/evidence/example-request.json
```

With no accepted model, this returns `available: false`,
`status: unavailable`, `reasons: ["missing_accepted_model"]` and **no**
`prediction` or confidence field. The CLI exits 2 intentionally.

Other statuses:

| Status | Meaning |
|---|---|
| `unsupported_input` | Unrecognized crop/scenario, invalid schema/units/coordinates/period/depth |
| `insufficient_evidence` | Missing features, unavailable/ineligible source, or outside validated support |
| `unavailable` | No accepted compatible model, corrupt bundle, execution failure |
| `supported_prediction` | Accepted model and conservative support checks passed; `prediction` is an index |

Every response includes target meaning/unit, reference period, source versions,
model/schema versions, missing features, input quality, limitations, coverage
status and availability reasons. Failures never contain a numeric score.

## If a future run is accepted

Only an operator-reviewed, trusted local `accepted.joblib` plus its matching
`evaluation.json` may be loaded. Joblib uses executable pickle: **never load
user uploads or arbitrary downloaded model files**. Checksums establish
consistency, not authorship. Loading checks acceptance evidence, exact contract,
library versions, source/target interpretation and artifact/dataset hashes.

The current support screen requires all of:

1. values within training numeric feature ranges;
2. joint standardized environmental distance within a validation-derived
   95th-percentile nearest-training threshold;
3. location inside a 10° block actually evaluated in the final holdout;
4. supported crop/scenario and required source/depth/period semantics.

These checks deliberately reject many otherwise plausible new locations.
They do **not** establish universal transferability or full Phase 5 reliability.
“Similar-region estimate” is reserved for later validated behavior and is not
currently emitted. No calibrated probability or confidence percentage exists.

Phase 3 retains responsibility for crop-family history, planting calendars,
water accounting, management references, rotations, priorities and constraints.
It may show a future suitability index as separate evidence, never as a proven
rotation benefit. Keep the model version and limitations with any later
persistence, and never overwrite the reference-based report status.
