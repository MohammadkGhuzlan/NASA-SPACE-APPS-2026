"""Owned HTTP run -> worker -> saved report, using isolated software fixtures.

Database changes are rolled back; source fixtures only live in a TemporaryDirectory.
No training, live downloads, scientific accuracy claims, or permanent farm changes.
"""
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.main import app
from backend.database import engine, get_db
from backend.experimental import inputs, reporting, routes
from backend.experimental.models import WARNING
from backend.machine_learning.common import read_json, write_json
from backend.machine_learning.farm_inputs import prepare_location

SOIL = {"clay_pct": 20., "sand_pct": 40., "silt_pct": 40., "ph": 7., "soc_g_kg": 15.}
CLIMATE = {**{f"tmean_m{i:02d}": 20. for i in range(1, 13)},
           **{f"rain_m{i:02d}": 30. for i in range(1, 13)}}


class EstimateFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.connection = engine.connect()
        self.transaction = self.connection.begin()
        self.db = Session(bind=self.connection, join_transaction_mode="create_savepoint")
        app.dependency_overrides[get_db] = lambda: self.db
        self.client = TestClient(app)
        self.stack = ExitStack()
        for module in [routes, reporting]:
            self.stack.enter_context(patch.object(module, "ROOT", self.root))
            self.stack.enter_context(patch.object(module, "manifest", return_value={
                "modelVersion": "software-fixture", "models": {"BRL": {"sha256": "fixture-hash"}}}))
        self.stack.enter_context(patch.object(routes, "status", return_value={"available": True}))
        self.stack.enter_context(patch.object(routes, "WORKFLOW_ENABLED", True))
        routes.active = None
        routes.recent.clear()
        response = self.client.post("/api/farms", json={
            "name": "Software fixture, rolled back", "locationName": "Isolated flow fixture",
            "latitude": 34.5004, "longitude": -91.5526, "currentCrop": "Barley",
            "irrigation": "rainfed", "goal": "soil_health"})
        self.assertEqual(response.status_code, 201)
        self.farm_id = response.json()["id"]

    def tearDown(self):
        self.stack.close()
        self.client.close()
        app.dependency_overrides.clear()
        self.db.close()
        self.transaction.rollback()
        self.connection.close()
        self.temp.cleanup()
        routes.active = None
        routes.recent.clear()

    def complete(self, *, local=True, climate=True, proxy=True, allow=True):
        def prepare_worker(command, **kwargs):
            # Run the actual preparation/fallback functions with source fixtures,
            # replacing only network/raster IO at this subprocess boundary.
            with patch("backend.machine_learning.farm_inputs.acquire_power",
                       return_value=(CLIMATE, {"source": "NASA POWER", "path": "/private-fixture"})) as power, \
                 patch("backend.machine_learning.farm_inputs.acquire_soil",
                       side_effect=ValueError("Soil_insufficient_valid_area:0.922")), \
                 patch.object(inputs, "download", return_value={}), \
                 patch.object(inputs, "native_soil_mean") as native, \
                 patch.object(inputs, "nearest_training_soil") as nearest:
                if not climate:
                    power.side_effect = ValueError("incomplete_climate_years")
                if local:
                    native.side_effect = lambda path, *a, **kw: (
                        SOIL[inputs.SOIL_PROPERTIES[path.name.split("_")[0]]],
                        {"valid_area_fraction": .922, "source": "ISRIC SoilGrids", "path": "/private-fixture"})
                else:
                    native.side_effect = ValueError("Soil_insufficient_valid_area:0.000")
                if proxy:
                    nearest.return_value = (SOIL, {
                        "method": "nearest_recorded_training_cell", "estimated": True,
                        "distanceKm": 350., "sourceCellId": "fixture-training-cell",
                        "sourceCoordinates": {"latitude": 32., "longitude": 35.},
                        "source": "ISRIC SoilGrids verified training cache",
                        "sourceEvidence": {"clay": {"source": "ISRIC SoilGrids"}}})
                else:
                    nearest.side_effect = ValueError("Soil_proxy_dataset_integrity_failure")
                prep = prepare_location(34.5004, -91.5526, "BRL", "LRLM", self.root)
                prep = inputs.allow_soil_estimates(prep, self.root, allow=allow)
                write_json(Path(command[command.index("--output") + 1]), prep)

        with patch.object(routes.pool, "submit") as submit:
            response = self.client.post(f"/api/farms/{self.farm_id}/experimental-ml",
                json={"cropCode": "BRL", "acknowledgeWarning": True, "allowEstimatedInputs": allow})
        self.assertEqual(response.status_code, 200)
        # Invoke after route admission releases the lock, just as a real worker does.
        fn, *args = submit.call_args.args
        output = {"value": 1234., "unit": "Index", "estimatorExecuted": True,
                  "productionAccepted": False, "artifactSha256": "fixture-hash", "warnings": [WARNING]}
        with patch.object(routes.subprocess, "run", side_effect=prepare_worker), \
             patch.object(routes, "infer", return_value=output) as estimator:
            fn(*args)
        job_id = response.json()["jobId"]
        response = self.client.get(f"/api/farms/{self.farm_id}/experimental-ml/jobs/{job_id}")
        self.assertEqual(response.status_code, 200)
        return response.json(), estimator.call_count

    def test_partial_local_and_remote_proxy_survive_owned_report_snapshot(self):
        for local in [True, False]:
            with self.subTest(local=local):
                routes.recent.clear()
                # Explicit retries permit recomputation without changing farm data.
                for path in (self.root / "jobs").glob("*"):
                    path.unlink()
                job, count = self.complete(local=local)
                self.assertEqual(count, 1)
                self.assertEqual(job["status"], "experimental_output")
                summary = job["inputSummary"]
                self.assertTrue(summary["estimatedInputs"])
                self.assertFalse(summary["compatible"])
                self.assertNotIn("/private-fixture", str(summary))
                if local:
                    self.assertEqual(summary["soilEstimation"]["validAreaFractions"]["clay"], .922)
                else:
                    self.assertEqual(summary["soilEstimation"]["distanceKm"], 350.)
                    self.assertEqual(summary["soilEstimation"]["sourceCellId"], "fixture-training-cell")
                outsider = TestClient(app)
                r = outsider.get(f"/api/farms/{self.farm_id}/experimental-ml/jobs/{job['jobId']}")
                outsider.close()
                self.assertEqual(r.status_code, 404)
                context = {"status": "unavailable", "monthly": [], "annual": [], "provenance": [],
                           "availableParameters": [], "referencePeriod": "fixture", "warnings": []}
                with patch("backend.recommendation.routes.check_analysis_rate"), \
                     patch("backend.recommendation.routes.ensure_environment", return_value=None), \
                     patch("backend.recommendation.routes.summary_for", return_value=context), \
                     patch("backend.recommendation.routes.build_features", return_value={"soilInputs": {}}), \
                     patch("backend.recommendation.routes.soil_context", return_value={}), \
                     patch("backend.recommendation.routes.integrate_evidence", side_effect=lambda *a, **kw: a[4]):
                    result = self.client.post(f"/api/farms/{self.farm_id}/plans", json={"currentRotation": ["Barley"]})
                self.assertEqual(result.status_code, 201, result.text)
                report_id = result.json()["id"]
                # Disposable job updates must not rewrite a saved report.
                path = self.root / "jobs" / f"{job['jobId']}.json"
                record = read_json(path)
                write_json(path, {**record, "value": 9999., "inputSummary": {}})
                saved = self.client.get(f"/api/farms/{self.farm_id}/plans/{report_id}").json()
                snapshot = saved["mlPredictions"]["jobs"][0]
                self.assertEqual(snapshot["inputSummary"], job["inputSummary"])
                self.assertEqual(snapshot["warnings"], job["warnings"])
                self.assertEqual(snapshot["value"], 1234.)
                self.assertNotIn("ownerHash", snapshot)

    def test_missing_climate_invalid_proxy_and_opt_out_are_explicit_refusals(self):
        cases = [
            ({"climate": False}, "climate"),
            ({"local": False, "proxy": False}, "proxy"),
            ({"allow": False}, "Enable estimated soil"),
        ]
        for options, reason in cases:
            with self.subTest(options=options):
                routes.recent.clear()
                for path in (self.root / "jobs").glob("*"):
                    path.unlink()
                job, count = self.complete(**options)
                self.assertEqual(count, 0)
                self.assertEqual(job["status"], "missing_inputs")
                self.assertIsNone(job["value"])
                self.assertIn(reason, " ".join(job["reasons"]))
                self.assertIsNotNone(job["inputSummary"]["operationalRefusal"])


if __name__ == "__main__":
    unittest.main()
