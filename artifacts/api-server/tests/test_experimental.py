"""Software fixtures only. Authentic inference is separately checked end to end."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.experimental import models, routes
from backend.experimental.operator import owner_hash
from backend.machine_learning.common import write_json


class ExperimentalTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.patches = [patch.object(models, "ROOT", self.root),
                        patch.object(routes, "ROOT", self.root),
                        patch.object(routes, "WORKFLOW_ENABLED", False),
                        patch.dict(os.environ, {"NODE_ENV": "development"})]
        for p in self.patches:
            p.start()
        self.farm = SimpleNamespace(id=9001, owner="software-fixture-owner",
                    profile={"latitude": 34.5, "longitude": -91.5})
        routes.active = None
        routes.recent.clear()
        models._load.cache_clear()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.temp.cleanup()
        routes.active = None
        routes.recent.clear()
        models._load.cache_clear()

    def grant(self):
        write_json(self.root / "access.json",
                   {"enabled": True, "owners": [owner_hash(self.farm.owner)]})

    def client(self):
        app = FastAPI()
        app.include_router(routes.router)
        app.dependency_overrides[routes.get_db] = lambda: None
        return TestClient(app)

    def test_access_default_denied(self):
        self.assertFalse(routes.authorized(self.farm))

    def test_access_operator_grant_and_isolation(self):
        self.grant()
        self.assertTrue(routes.authorized(self.farm))
        self.assertFalse(routes.authorized(SimpleNamespace(owner="different-owner")))

    def test_production_always_denied(self):
        self.grant()
        with patch.dict(os.environ, {"NODE_ENV": "production"}):
            self.assertFalse(routes.authorized(self.farm))

    def test_all_development_users_still_blocks_production(self):
        write_json(self.root / "access.json", {"enabled": True, "allDevelopmentUsers": True, "owners": []})
        self.assertTrue(routes.authorized(self.farm))
        self.assertTrue(routes.authorized(SimpleNamespace(owner="another-workspace")))
        with patch.dict(os.environ, {"NODE_ENV": "production"}):
            self.assertFalse(routes.authorized(self.farm))

    def test_missing_runtime_mode_denied(self):
        self.grant()
        with patch.dict(os.environ, {"NODE_ENV": ""}):
            self.assertFalse(routes.authorized(self.farm))

    def test_corrupt_access_fails_closed(self):
        (self.root / "access.json").write_text("not-json")
        self.assertFalse(routes.authorized(self.farm))

    def test_authorized_missing_models_unavailable(self):
        self.grant()
        self.assertEqual(routes.status(self.farm)["reason"], "verified_experimental_artifacts_unavailable")
        self.assertFalse(routes.status(self.farm)["productionPredictionsEnabled"])

    def test_hash_mismatch_never_deserializes(self):
        path = self.root / "models" / "WHE-experimental.joblib"
        path.parent.mkdir()
        path.write_bytes(b"fixture-corrupted")
        with patch.object(models.joblib, "load") as loader:
            with self.assertRaises(ValueError):
                models._load("WHE", "bad-hash", "manifest-fixture")
            loader.assert_not_called()

    def test_manifest_rejects_production_promotion(self):
        write_json(self.root / "manifest.json", {"mode": "production"})
        with self.assertRaises((KeyError, ValueError)):
            models.manifest()

    def test_unknown_crop_request_rejected(self):
        with self.assertRaises(ValueError):
            routes.ExperimentalInput(cropCode="FAKE", acknowledgeWarning=True)

    def test_acknowledgment_required(self):
        with self.assertRaises(ValueError):
            routes.ExperimentalInput(cropCode="WHE", acknowledgeWarning=False)

    def test_client_cannot_override_features_paths_or_coordinates(self):
        for key in ["features", "modelPath", "latitude", "scenario", "owner"]:
            with self.assertRaises(ValueError):
                routes.ExperimentalInput(cropCode="WHE", acknowledgeWarning=True, **{key: "untrusted"})

    def test_http_authorization_enforced(self):
        with patch.object(routes, "owned_farm", return_value=self.farm):
            r = self.client().post("/api/farms/9001/experimental-ml",
                json={"cropCode": "WHE", "acknowledgeWarning": True})
        self.assertEqual(r.status_code, 403)

    def test_http_missing_model_no_feature_job(self):
        self.grant()
        with patch.object(routes, "owned_farm", return_value=self.farm), patch.object(routes.pool, "submit") as submit:
            r = self.client().post("/api/farms/9001/experimental-ml",
                json={"cropCode": "WHE", "acknowledgeWarning": True})
        self.assertEqual(r.status_code, 503)
        submit.assert_not_called()

    def test_job_owner_not_found(self):
        self.grant()
        key = "a"*64
        write_json(self.root / "jobs" / f"{key}.json", {"farmId": 9001, "ownerHash": "another-owner"})
        with patch.object(routes, "owned_farm", return_value=self.farm):
            r = self.client().get(f"/api/farms/9001/experimental-ml/jobs/{key}")
        self.assertEqual(r.status_code, 404)

    def test_job_coordinates_changed_refused(self):
        self.grant()
        key = "a"*64
        write_json(self.root / "jobs" / f"{key}.json",
            {"farmId": 9001, "ownerHash": owner_hash(self.farm.owner),
             "requestedCoordinates": {"latitude": 1, "longitude": 1}})
        with patch.object(routes, "owned_farm", return_value=self.farm):
            r = self.client().get(f"/api/farms/9001/experimental-ml/jobs/{key}")
        self.assertEqual(r.status_code, 409)

    def test_interrupted_job_not_stuck(self):
        self.grant()
        key = "a"*64
        write_json(self.root / "jobs" / f"{key}.json",
            {"farmId": 9001, "ownerHash": owner_hash(self.farm.owner),
             "requestedCoordinates": {"latitude": 34.5, "longitude": -91.5}, "status": "preparing"})
        with patch.object(routes, "owned_farm", return_value=self.farm):
            r = self.client().get(f"/api/farms/9001/experimental-ml/jobs/{key}")
        self.assertEqual(r.json()["status"], "interrupted")
        self.assertNotIn("ownerHash", r.json())

    def test_single_flight_and_cooldown(self):
        self.grant()
        data = {"cropCode": "WHE", "acknowledgeWarning": True}
        with patch.object(routes, "owned_farm", return_value=self.farm), \
             patch.object(routes, "status", return_value={"available": True}), \
             patch.object(routes, "manifest", return_value={"modelVersion": "unit-fixture"}), \
             patch.object(routes.pool, "submit") as submit:
            client = self.client()
            first = client.post("/api/farms/9001/experimental-ml", json=data)
            again = client.post("/api/farms/9001/experimental-ml", json=data)
            other = client.post("/api/farms/9001/experimental-ml",
                               json={**data, "cropCode": "BRL"})
            self.assertEqual(first.json()["jobId"], again.json()["jobId"])
            self.assertEqual(other.status_code, 429)
            self.assertEqual(submit.call_count, 1)

    def test_missing_features_not_substituted(self):
        with self.assertRaises((ValueError, KeyError)):
            models.infer({"crop": "WHE", "scenario": "LRLM"}, 34.5, -91.5)

    def test_pruning_bounds_only_disposable_experimental_jobs(self):
        for index in range(257):
            write_json(self.root / "jobs" / (f"{index:064x}.json"), {"fixture": True})
        write_json(self.root / "manifest.json", {"mustRemain": True})
        routes.prune_jobs()
        self.assertEqual(len(list((self.root / "jobs").glob("*.json"))), 255)
        self.assertTrue((self.root / "manifest.json").exists())


if __name__ == "__main__":
    unittest.main()
