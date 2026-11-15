"""Software fixtures only; no synthetic vectors are used for live predictions."""
from copy import deepcopy
import inspect
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from backend.experimental import inputs, policy, reporting, routes
from backend.experimental.models import WARNING
from backend.experimental.operator import owner_hash
from backend.machine_learning.common import digest, sha256, write_json
from backend.machine_learning.environment import native_soil_mean

SOIL = {"clay_pct": 20., "sand_pct": 40., "silt_pct": 40., "ph": 7., "soc_g_kg": 15.}
CLIMATE = {**{f"tmean_m{x:02d}": 20. for x in range(1, 13)},
           **{f"rain_m{x:02d}": 30. for x in range(1, 13)}}


def prepared():
    return {"compatible": False, "crop": "MZE", "selected_coordinates": {"latitude": 30., "longitude": 35.},
            "climate_features": CLIMATE.copy(), "reasons": ["ValueError:Soil_insufficient_valid_area:0.42"],
            "label_cell": {"latitude": 30.041666, "longitude": 35.041666, "cell_id": "fixture"},
            "model_request": None}


class EstimatedInputTests(unittest.TestCase):
    def test_strict_native_default_stays_95_percent(self):
        self.assertEqual(inspect.signature(native_soil_mean).parameters["minimum_valid_area"].default, .95)

    def test_complete_input_no_estimation(self):
        p = {**prepared(), "compatible": True}
        with patch.object(inputs, "native_soil_mean") as source:
            result = inputs.allow_soil_estimates(p, Path("/unused"))
        source.assert_not_called()
        self.assertTrue(result["experimental_usable"])
        self.assertFalse(result["estimated_inputs"])

    def test_opt_out_and_missing_climate_never_estimated(self):
        for p, allow in [(prepared(), False), ({**prepared(), "climate_features": {}}, True)]:
            with patch.object(inputs, "native_soil_mean") as source:
                r = inputs.allow_soil_estimates(p, Path("/unused"), allow=allow)
            source.assert_not_called()
            self.assertFalse(r["experimental_usable"])
            self.assertIsNone(r["model_request"])

    def test_partial_coverage_preserves_real_climate_and_marks_mismatch(self):
        def native(path, lat, lon, root, **kwargs):
            self.assertEqual(kwargs["minimum_valid_area"], .1)
            prop = path.name.split("_")[0]
            return SOIL[inputs.SOIL_PROPERTIES[prop]], {"valid_area_fraction": .42, "path": "/internal"}
        with patch.object(inputs, "native_soil_mean", side_effect=native):
            r = inputs.allow_soil_estimates(prepared(), Path("/unused"))
        self.assertFalse(r["compatible"])
        self.assertTrue(r["experimental_usable"])
        self.assertTrue(r["estimated_inputs"])
        self.assertEqual(r["model_request"]["features"]["rain_m01"], CLIMATE["rain_m01"])
        self.assertEqual(r["soil_estimation"]["distanceKm"], 0)
        self.assertNotIn("path", r["soil_estimation"]["sourceEvidence"]["clay"])

    def test_remote_proxy_is_disclosed_not_local_measurement(self):
        proxy = {"distanceKm": 500., "method": "nearest_recorded_training_cell"}
        with patch.object(inputs, "native_soil_mean", side_effect=ValueError("Soil_insufficient_valid_area:0.000")), \
                patch.object(inputs, "nearest_training_soil", return_value=(SOIL, proxy)):
            r = inputs.allow_soil_estimates(prepared(), Path("/unused"))
        self.assertIn("500.0 km away", r["input_warnings"][0])
        self.assertFalse(r["compatible"])
        self.assertEqual(r["model_request"]["features"]["ph"], 7.)

    def test_invalid_proxy_not_filled_or_predicted(self):
        with patch.object(inputs, "native_soil_mean", side_effect=ValueError("unavailable")), \
                patch.object(inputs, "nearest_training_soil", return_value=({**SOIL, "ph": None}, {"distanceKm": 1})):
            with self.assertRaises(ValueError):
                inputs.allow_soil_estimates(prepared(), Path("/unused"))

    def test_proxy_failure_does_not_produce_fallback_numbers(self):
        with patch.object(inputs, "native_soil_mean", side_effect=ValueError("unavailable")), \
                patch.object(inputs, "nearest_training_soil", side_effect=ValueError("no verified proxy")):
            with self.assertRaises(ValueError):
                inputs.allow_soil_estimates(prepared(), Path("/unused"))

    def test_antimeridian_distance(self):
        self.assertAlmostEqual(inputs.distance_km(0, 179, 0, -179), 222.39, places=1)

    def test_only_training_cells_can_be_soil_proxies(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            rows = [{"cell_id": cid, "crop": "MZE", "latitude": lat, "longitude": 0,
                     **SOIL, "soil_evidence": {}} for cid, lat in [("train", 1), ("test", 0)]]
            bundle = {"records": rows}
            checksum = digest(bundle)
            write_json(root / "generated-artifacts/ml-recovery/experimental-restored/dataset.json",
                       {**bundle, "dataset_hash": checksum})
            path = root / "docs/ml-recovery/evidence/expanded-evaluation.json"
            write_json(path, {"splits": [{"cell_id": "train", "crop": "MZE", "split": "train"},
                                        {"cell_id": "test", "crop": "MZE", "split": "test"}]})
            info = {"datasetHash": checksum, "sourceEvaluationSha256": sha256(path)}
            with patch.object(inputs, "ROOT", root / "generated-artifacts/experimental-ml"), \
                    patch.object(inputs, "manifest", return_value=info):
                soil, source = inputs.nearest_training_soil(0, 0)
                self.assertEqual(source["sourceCellId"], "train")
                self.assertGreater(source["distanceKm"], 100)
                write_json(path, {"splits": []})
                with self.assertRaisesRegex(ValueError, "integrity"):
                    inputs.nearest_training_soil(0, 0)

    def test_operational_enablement_not_acceptance(self):
        with patch("backend.experimental.models.manifest", return_value={}), \
                patch.object(policy, "WORKFLOW_ENABLED", True):
            s = policy.operational_status()
        self.assertTrue(s["predictionsEnabled"])
        self.assertEqual(s["state"], "unvalidated_enabled")
        self.assertFalse(s["scientificallyValidated"])

    def test_missing_artifacts_not_advertised_as_working(self):
        with patch("backend.experimental.models.manifest", side_effect=ValueError("missing")):
            self.assertFalse(policy.operational_status()["predictionsEnabled"])

    def test_new_workflow_public_even_outside_development(self):
        with patch.object(routes, "WORKFLOW_ENABLED", True), \
                patch.dict("os.environ", {"NODE_ENV": "production"}):
            self.assertTrue(routes.authorized(SimpleNamespace(owner="fixture")))


class SavedEstimateTests(unittest.TestCase):
    def test_owned_zero_output_is_snapshotted_and_other_workspaces_excluded(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            farm = SimpleNamespace(id=1, owner="fixture", profile={"latitude": 32., "longitude": 35.})
            job = {"farmId": 1, "ownerHash": owner_hash(farm.owner),
                   "requestedCoordinates": farm.profile, "inputPolicy": reporting.INPUT_POLICY,
                   "cropCode": "MZE", "jobId": "a"*64, "status": "experimental_output",
                   "createdAt": "2026-11-15T00:00:00Z", "value": 0.,
                   "estimatorExecuted": True, "productionAccepted": False,
                   "artifactSha256": "verified", "warning": WARNING,
                   "inputQuality": "estimated_soil", "inputSummary": {"estimatedInputs": True}}
            for i, changes in enumerate([{}, {"farmId": 2}, {"ownerHash": "other"},
                                          {"requestedCoordinates": {"latitude": 0, "longitude": 0}},
                                          {"inputPolicy": "old"}, {"artifactSha256": "wrong"}]):
                write_json(root / "jobs" / (f"{i:064x}.json"), {**job, **changes})
            info = {"models": {"MZE": {"sha256": "verified"}}}
            with patch.object(reporting, "ROOT", root), patch.object(reporting, "manifest", return_value=info):
                snap = reporting.snapshot_for(farm)
                self.assertEqual(len(snap["jobs"]), 1)
                self.assertEqual(snap["jobs"][0]["value"], 0.)
                self.assertNotIn("ownerHash", snap["jobs"][0])
                original = {"candidates": [{"crop": {"name": "Maize"}, "status": "reference"}],
                            "aiIntegration": {"model": {"message": "Legacy unavailable"},
                                              "warnings": ["Legacy unavailable", "Scientific validation failed"],
                                              "plannerUse": "old"}}
                before = deepcopy(original)
                with patch.object(reporting, "operational_status", return_value={
                        "predictionsEnabled": True, "message": "Enabled, unvalidated."}):
                    report = reporting.attach_predictions(farm, original)
                self.assertEqual(original, before)
                self.assertEqual(len(report["candidates"][0]["modelEstimates"]), 1)
                self.assertNotIn("Legacy unavailable", report["aiIntegration"]["warnings"])
                self.assertIn("Scientific validation failed", report["aiIntegration"]["warnings"])
                write_json(root / "jobs" / ("0"*64+".json"), {**job, "value": 999.})
                self.assertEqual(report["mlPredictions"]["jobs"][0]["value"], 0.)
