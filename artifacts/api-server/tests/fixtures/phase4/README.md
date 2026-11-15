# Authentic source fixtures

`gaez_cells.json` contains 25 actual catalog-traceable suitability labels
(five sampled cells × five crop types). `gaez_brl_window.tif` is a 3×3 unmodified
pixel window from the corresponding barley raster; the JSON records its hash,
parent raster hash, window offset, exact download URL and attribution.

Source: FAO/IIASA, GAEZ v5, RES05-SXX, AgERA5 historical 2001–2020, rain-fed
low-input management. Index 0–10,000, scale 1, NoData −9, WGS84, 5 arc minutes.
Reuse: CC BY 4.0. Pixel subsetting and packaging by Field Shift.

These small fixtures exercise authentic source parsing offline. They are
**not** an aligned ML dataset, independent crop outcomes, or a global benchmark.
The synthetic data/models in `test_machine_learning.py` are separate software
tests only; temporary pickles are removed with their temporary directories.

Regenerate fixtures and their factual source audit only from hash-verified
official files using the `audit` command in `docs/phase4/REPRODUCE.md`.
