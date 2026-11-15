"""Recovery software tests: synthetic test-only metrics, never scientific evidence."""
from dataclasses import asdict
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

from backend.machine_learning.budget import ResearchBudget, BudgetExceeded
from backend.machine_learning.contract import NUMERIC
from backend.machine_learning.farm_inputs import label_cell, prepare_location
from backend.machine_learning.holdout import reserve
from backend.machine_learning.recovery_training import gates, domain_regions
from backend.machine_learning.common import write_json


def report(mae=100, r2=.9, cells=25, baseline=1000):
    score = {"mae": mae, "r2": r2, "rmse": mae, "count": cells}
    return {"candidate": {"aggregate": score, "geographic_blocks": 6,
                          "per_region": {"test_only_region": {"cells": cells, "mae": mae}}},
            "mean": {"aggregate": {"mae": baseline}},
            "median": {"aggregate": {"mae": baseline}}}


class RecoverySafetyTests(unittest.TestCase):
    def test_geographic_holdout_cannot_be_reused_with_new_dataset_hash(self):
        with tempfile.TemporaryDirectory() as root:
            reserve(["1:2", "1:3"], seed=42, run_identity={"dataset": "TEST_ONLY_A"}, root=root)
            with self.assertRaisesRegex(ValueError, "already_consumed"):
                reserve(["1:3", "2:3"], seed=42, run_identity={"dataset": "TEST_ONLY_B"}, root=root)
            with self.assertRaisesRegex(ValueError, "already_consumed"):
                reserve(["1:3"], seed=99, run_identity={"dataset": "TEST_ONLY_C"}, root=root)
            reserve(["2:3"], seed=42, run_identity={"dataset": "TEST_ONLY_B"}, root=root)

    def test_corrupt_holdout_ledger_fails_closed(self):
        with tempfile.TemporaryDirectory() as root:
            Path(root, "reservation-corrupt.json").write_text("{}")
            with self.assertRaises(KeyError):
                reserve(["1:2"], seed=42, run_identity={}, root=root)

    def test_empty_holdout_is_not_valid(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(ValueError, "empty"):
                reserve([], seed=42, run_identity={}, root=root)

    def test_crop_acceptance_is_independent(self):
        self.assertEqual(gates(report()), [])
        self.assertIn("mae", gates(report(mae=2000)))
        self.assertEqual(gates(report()), [])  # another crop does not inherit rejection

    def test_all_visible_rejection_reasons_are_reported(self):
        reasons = gates(report(mae=2000, r2=0, cells=3))
        for expected in ("mae", "r2", "insufficient_independent_cells",
                         "no_meaningful_mean_improvement", "no_meaningful_median_improvement"):
            self.assertIn(expected, reasons)
        self.assertTrue(any(x.startswith("insufficient_region_cells") for x in reasons))

    def test_mae_pass_alone_cannot_consume_test(self):
        self.assertIn("r2", gates(report(mae=100, r2=.1)))
        self.assertIn("no_meaningful_mean_improvement", gates(report(mae=100, baseline=105)))

    def test_nonfinite_metrics_fail_closed(self):
        self.assertIn("nonfinite_metrics", gates(report(mae=float("nan"))))
        self.assertIn("r2", gates(report(r2=float("nan"))))

    def test_missing_declared_region_fails(self):
        self.assertIn("no_supported_region", gates(report(), minimum_regions=2))

    def test_scope_is_chosen_by_train_validation_counts_not_test_targets(self):
        train = pd.DataFrame([{"region": r, "cell_id": f"{r}-{i}"} for r, n in [("a", 10), ("b", 9)] for i in range(n)])
        va = pd.DataFrame([{"region": r, "cell_id": f"va-{r}-{i}"} for r, n in [("a", 5), ("b", 100)] for i in range(n)])
        self.assertEqual(domain_regions(train, va), ["a"])

    def test_resource_limits_fail_explicitly(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(BudgetExceeded, "time_budget"):
                ResearchBudget(root, seconds=0).check()
            Path(root, "source").write_bytes(b"TEST_ONLY")
            with self.assertRaisesRegex(BudgetExceeded, "cache_budget"):
                ResearchBudget(root, max_bytes=1).check()

    def test_exact_selected_coordinate_identity_and_cell_center(self):
        point = label_cell(37.8882, -4.7794)
        self.assertEqual(point["cell_id"], "RES05-SXX:625:2102")
        self.assertAlmostEqual(point["latitude"], 37.875)
        self.assertAlmostEqual(point["longitude"], -4.791666666666667)

    def test_boundaries_do_not_substitute_another_location(self):
        for lat, lon in [(0, 180), (-90, 0), (float("nan"), 0), (91, 0)]:
            with self.assertRaises(ValueError):
                label_cell(lat, lon)

    def test_unsupported_crop_and_management_do_not_download(self):
        with patch("backend.machine_learning.farm_inputs.acquire_power", side_effect=AssertionError("must not download")):
            self.assertEqual(prepare_location(20, 30, "rice", "LRLM", "unused")["reasons"], ["unsupported_crop"])
            self.assertEqual(prepare_location(20, 30, "WHE", "HILM", "unused")["reasons"], ["unsupported_management_scenario"])

    def test_missing_soil_keeps_authentic_partial_provenance_but_no_vector(self):
        with patch("backend.machine_learning.farm_inputs.acquire_power", return_value=({"TEST_ONLY": 1}, {"source": "TEST_ONLY"})), \
             patch("backend.machine_learning.farm_inputs.acquire_soil", side_effect=ValueError("TEST_ONLY_missing_soil")):
            result = prepare_location(37.8882, -4.7794, "WHE", "LRLM", "unused")
        self.assertFalse(result["compatible"])
        self.assertIsNone(result["model_request"])
        self.assertEqual(result["provenance"]["climate"]["source"], "TEST_ONLY")
        self.assertEqual(result["selected_coordinates"], {"latitude": 37.8882, "longitude": -4.7794})

    def test_builder_reuses_exact_contract_and_actual_transform_outputs(self):
        features = {**{f"tmean_m{m:02}": 15 for m in range(1, 13)},
                    **{f"rain_m{m:02}": 50 for m in range(1, 13)}}
        soil = {"clay_pct": 30, "sand_pct": 40, "silt_pct": 30, "ph": 7, "soc_g_kg": 15}
        with patch("backend.machine_learning.farm_inputs.acquire_power", return_value=(features, {"source": "TEST_ONLY"})) as power, \
             patch("backend.machine_learning.farm_inputs.acquire_soil", return_value=(soil, {})) as native:
            result = prepare_location(37.8882, -4.7794, "WHE", "LRLM", "TEST_ONLY")
        self.assertTrue(result["compatible"])
        self.assertEqual(result["model_request"]["period"], [2001, 2020])
        self.assertEqual(result["model_request"]["latitude"], result["label_cell"]["latitude"])
        self.assertEqual(result["model_request"]["longitude"], result["label_cell"]["longitude"])
        self.assertEqual(result["selected_coordinates"], {"latitude": 37.8882, "longitude": -4.7794})
        self.assertEqual(set(result["model_request"]["features"]), set(NUMERIC) | {"crop", "scenario"})
        self.assertEqual(power.call_args.args[:2], native.call_args.args[:2])

    def test_per_crop_training_records_diagnostics_without_consuming_test(self):
        from sklearn.linear_model import Ridge
        from backend.machine_learning.recovery_training import fit
        # Entirely synthetic plumbing check, never included in scientific reports.
        rows = []
        for lat in range(-55, 66, 10):
            for lon in range(-175, 176, 10):
                value = (lat+lon+250) % 60
                rows.append({
                    **{f"tmean_m{m:02}": float(value-20) for m in range(1, 13)},
                    **{f"rain_m{m:02}": float(value+1) for m in range(1, 13)},
                    "clay_pct": 30., "sand_pct": 40., "silt_pct": 30., "ph": 7.,
                    "soc_g_kg": 15., "crop": "WHE", "scenario": "LRLM",
                    "latitude": float(lat), "longitude": float(lon),
                    "cell_id": f"TEST_ONLY:{lat}:{lon}", "target": float(value*150)})
        with tempfile.TemporaryDirectory() as root:
            path = Path(root, "dataset.json")
            write_json(path, {"dataset_hash": "TEST_ONLY", "source_manifest": {}})
            with patch("backend.machine_learning.recovery_training.validate_dataset", return_value=pd.DataFrame(rows)), \
                 patch("backend.machine_learning.recovery_training.CROPS", {"WHE": "TEST_ONLY"}), \
                 patch("backend.machine_learning.recovery_training.RandomForestRegressor", return_value=Ridge()), \
                 patch("backend.machine_learning.recovery_training.HistGradientBoostingRegressor", return_value=Ridge()), \
                 patch("backend.machine_learning.recovery_training.domain_regions", return_value=[]), \
                 patch("backend.machine_learning.holdout.reserve", side_effect=AssertionError("must not consume test")):
                result = fit(path, Path(root, "out"))
            self.assertEqual(result["accepted_crops"], [])
            self.assertFalse(result["final_test_evaluated"])
            self.assertFalse(result["model_saved"])
            self.assertEqual(len(result["crops"]["WHE"]["candidates"]), 5)
            self.assertIn("nonspatial_cell_grouped", result["crops"]["WHE"]["candidates"]["histogram"]["cv"])
            self.assertFalse(list(Path(root).rglob("*.joblib")))


if __name__ == "__main__":
    unittest.main()
