# Recorded real-data evaluation

Outcome: **rejected_on_validation**.

These metrics, when present, approximate modeled GAEZ index values (0–10,000); they are not observed crop success or yield.

## Geographic sample counts

| Partition | Independent source cells |
|---|---:|
| test | 26 |
| train | 74 |
| validation | 24 |

## Training-only CV and validation

| Candidate | Mean fold MAE | Validation MAE | Validation RMSE | Validation R² |
|---|---:|---:|---:|---:|
| forest_leaf_3 | 1294.336 | 1672.801 | 2535.843 | 0.057 |
| forest_leaf_8 | 1308.261 | 1720.740 | 2537.041 | 0.056 |
| ridge_1.0 | 1435.538 | 1800.651 | 2746.057 | -0.106 |
| ridge_10.0 | 1363.217 | 1772.500 | 2683.524 | -0.056 |

Fold MAE above is an unweighted mean of the three buffered training-only fold errors. Validation, not final-test performance, selected the candidate.

Selected candidate: **forest_leaf_3**.

Dummy mean baseline validation: MAE **1717.194**, RMSE **2635.068**, R² **-0.018**.

### Selected candidate validation by crop

| Group | Source cells | Rows | MAE | RMSE | R² |
|---|---:|---:|---:|---:|---:|
| BRL | 24 | 24 | 2026.640 | 3074.790 | -0.003 |
| MZE | 24 | 24 | 1751.589 | 2714.434 | 0.025 |
| RCD | 24 | 24 | 1369.467 | 1795.926 | 0.201 |
| RCW | 24 | 24 | 1265.771 | 1640.557 | 0.013 |
| WHE | 24 | 24 | 1950.537 | 3068.098 | -0.011 |

### Selected candidate validation by region

| Group | Source cells | Rows | MAE | RMSE | R² |
|---|---:|---:|---:|---:|---:|
| lat1_lon3 | 2 | 10 | 1507.132 | 1641.607 | -2.276 |
| lat1_lon4 | 2 | 10 | 832.268 | 911.381 | 0.102 |
| lat1_lon5 | 1 | 5 | 1109.535 | 1293.716 | 0.398 |
| lat2_lon1 | 2 | 10 | 4690.157 | 5136.129 | -0.403 |
| lat2_lon2 | 1 | 5 | 1384.244 | 1489.494 | -1.980 |
| lat2_lon3 | 1 | 5 | 2547.093 | 2558.278 | undefined |
| lat2_lon5 | 1 | 5 | 842.879 | 844.417 | undefined |
| lat3_lon1 | 1 | 5 | 797.979 | 920.568 | 0.753 |
| lat3_lon3 | 2 | 10 | 1795.515 | 2193.143 | 0.087 |
| lat4_lon1 | 3 | 15 | 3140.920 | 4588.685 | -0.382 |
| lat4_lon3 | 1 | 5 | 1606.669 | 1619.679 | -2.169 |
| lat4_lon4 | 3 | 15 | 949.285 | 1315.867 | 0.356 |
| lat4_lon5 | 1 | 5 | 836.199 | 866.318 | -77.178 |
| lat5_lon1 | 1 | 5 | 16.427 | 20.426 | undefined |
| lat5_lon2 | 1 | 5 | 1073.153 | 1080.119 | undefined |
| lat5_lon4 | 1 | 5 | 12.283 | 21.806 | undefined |

The final holdout was not evaluated.

## Readiness / rejection reasons

- `validation_mae`

Deployable model saved: **False**. A rejected candidate is not available for live predictions.
