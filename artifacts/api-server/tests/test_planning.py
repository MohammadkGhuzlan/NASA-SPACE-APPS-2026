"""Phase 3 rules, evidence boundaries and rollback-isolated API integration."""
import copy
import unittest
from datetime import date
from types import SimpleNamespace
from fastapi.testclient import TestClient
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from backend.main import app
from backend.database import engine, get_db
from backend.models import RecommendationResult, CropDefinition, CropRequirement
from backend.recommendation.knowledge import library, resolve, BY_ID, ensure_knowledge
from backend.recommendation.schemas import FarmingPlanInput
from backend.recommendation.engine import build_report, calendar_for, rotation_assessment


def fixture(profile=None, **kwargs):
    p = {"currentCrop": "Wheat", "goal": "soil_health", "irrigation": "rainfed",
         "latitude": 32.55696, "longitude": 35.84790, "cropHistory": "2024 barley"}
    p.update(profile or {})
    summary = {"availableParameters": ["T2M", "PRECTOTCORR"], "monthly": [
        {"period": "2025-01", "T2M": 12, "PRECTOTCORR": 10}],
        "annual": [], "referencePeriod": "2019–2025", "warnings": [],
        "location": {"latitude": p["latitude"], "longitude": p["longitude"]},
        "status": "available", "provenance": [{"source": "NASA POWER", "sourceUrl": "https://power.larc.nasa.gov/"}]}
    soil = {"ph": {"value": 7.9, "source": "PROXY_DEMO_ONLY"}}
    return build_report(SimpleNamespace(id=1, profile=p), FarmingPlanInput(**kwargs),
                        summary, {"soilInputs": soil, "irrigation": p["irrigation"]}, [])


class PlanningRulesTests(unittest.TestCase):
    def test_aliases_not_substring_guesses(self):
        self.assertEqual(resolve(" Corn "), "maize")
        self.assertIsNone(resolve("cornish pasture"))

    def test_reference_values(self):
        c = BY_ID["dry_bean"]
        self.assertEqual(c["growingDays"], [95, 110])
        self.assertEqual(c["waterMm"], [300, 500])

    def test_public_library_no_alias_internal_mutation(self):
        a = library()
        a["crops"][0]["waterMm"][0] = -10
        self.assertEqual(BY_ID["wheat"]["waterMm"], [450, 650])
        self.assertNotIn("aliases", library()["crops"][0])

    def test_no_trained_model_or_scores(self):
        r = fixture()
        self.assertEqual(r["modelStatus"], "not_trained")
        self.assertNotIn("confidence", r)
        self.assertNotIn("suitabilityScore", r["candidates"][0])
        self.assertEqual(r["status"], "reference_based_plan")

    def test_date_missing_remains_missing(self):
        self.assertIsNone(fixture()["candidates"][0]["calendar"]["harvestEarliest"])

    def test_leap_year_harvest_arithmetic(self):
        c = calendar_for(BY_ID["pea"], date(2028, 1, 1))
        self.assertEqual(c["harvestEarliest"], "2028-03-31")

    def test_zero_budget_not_missing(self):
        r = fixture(availableSeasonalWaterMm=0)
        self.assertTrue(all(c["status"] == "water_budget_conflict" for c in r["candidates"]))
        self.assertEqual(r["scenarios"][1]["status"], "insufficient_evidence")
        self.assertEqual(r["status"], "insufficient_evidence")

    def test_exclusions_respected(self):
        r = fixture(excludedCrops=["dry beans", "pea"])
        ids = {c["crop"]["id"] for c in r["candidates"]}
        self.assertNotIn("dry_bean", ids)
        self.assertNotIn("pea", ids)
        self.assertEqual(r["scenarios"][1]["crops"], [])

    def test_two_distinct_conditional_alternatives(self):
        r = fixture()
        a, b = r["scenarios"][1:]
        self.assertNotEqual(a["crops"], b["crops"])
        self.assertEqual(len(set(a["crops"])), 3)
        self.assertIn("conditional", a["status"])

    def test_unknown_current_crop_preserved_not_invented(self):
        r = fixture({"currentCrop": "Olive"})
        self.assertEqual(r["scenarios"][0]["crops"], ["Olive"])
        self.assertIsNone(r["scenarios"][0]["waterRequirementMm"])
        self.assertTrue(any(x["code"] == "unknown_crop" for x in r["scenarios"][0]["risks"]))

    def test_soil_proxy_not_ground_truth(self):
        r = fixture()
        self.assertEqual(r["environmentalEvidence"]["soilInputs"]["ph"]["source"], "PROXY_DEMO_ONLY")

    def test_scoped_maize_wheat_risk(self):
        _, risks = rotation_assessment(["maize", "wheat"])
        self.assertTrue(any(r["code"] == "maize_small_grain" and "Minnesota" in r["message"] for r in risks))

    def test_no_silent_history_parsing(self):
        r = fixture()
        self.assertTrue(any("not silently parsed" in x for x in r["missingInformation"]))
        self.assertEqual(r["inputs"]["planning"]["previousCrops"], [])

    def test_sequence_water_is_multi_cycle_not_budget(self):
        r = fixture(availableSeasonalWaterMm=700)
        self.assertTrue(any(x["code"] == "water_budget_scope" for x in r["scenarios"][1]["risks"]))

    def test_unknown_duration_blocks_later_calendar(self):
        r = fixture(currentRotation=["Olive", "Wheat"], plantingDate="2027-01-01")
        self.assertIsNone(r["scenarios"][0]["schedule"][1]["harvestEarliest"])

    def test_water_priority_not_fake_score(self):
        r = fixture({"goal": "conserve_water"})
        self.assertEqual(r["scenarios"][1]["crops"][0], "Dry bean")

    def test_invalid_requests(self):
        from pydantic import ValidationError
        for data in [{"availableSeasonalWaterMm": -1}, {"availableSeasonalWaterMm": float("nan")},
                     {"currentRotation": [""]}, {"plantingDate": "1900-01-01"}, {"unknown": 1}]:
            with self.assertRaises(ValidationError):
                FarmingPlanInput(**data)

    def test_snapshot_copies_profile(self):
        r = fixture(operationalLimitations="No potato harvester")
        self.assertEqual(r["inputs"]["planning"]["operationalLimitations"], "No potato harvester")
        self.assertTrue(any("not automatically interpreted" in x["message"] for x in r["candidates"][0]["risks"]))


class PlanningApiTests(unittest.TestCase):
    def setUp(self):
        self.connection = engine.connect()
        self.transaction = self.connection.begin()
        self.db = Session(bind=self.connection, join_transaction_mode="create_savepoint")
        app.dependency_overrides[get_db] = lambda: self.db
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        self.db.close()
        self.transaction.rollback()
        self.connection.close()

    def farm(self):
        response = self.client.post("/api/farms", json={"name": "Phase 3 isolated test",
            "locationName": "Irbid", "latitude": 32.55696, "longitude": 35.8479,
            "currentCrop": "Wheat", "irrigation": "rainfed", "goal": "soil_health"})
        self.assertEqual(response.status_code, 201)
        return response.json()["id"]

    def test_generate_save_reopen_owner_and_metadata(self):
        id = self.farm()
        r = self.client.post(f"/api/farms/{id}/plans", json={"plantingDate": "2027-02-01"})
        self.assertEqual(r.status_code, 201, r.text)
        report = r.json()
        self.assertEqual(len(report["scenarios"]), 3)
        self.assertEqual(report["environmentalEvidence"]["location"]["latitude"], 32.55696)
        pid = report["id"]
        self.assertEqual(self.client.get(f"/api/farms/{id}/plans/{pid}").json(), report)
        self.assertEqual(self.client.get(f"/api/farms/{id}/plans").json()[0]["id"], pid)
        row = self.db.get(RecommendationResult, pid)
        self.assertIsNone(row.model_id)
        self.assertIsNone(row.strategy_id)
        stranger = TestClient(app)
        try:
            self.assertEqual(stranger.get(f"/api/farms/{id}/plans/{pid}").status_code, 404)
            self.assertEqual(stranger.post(f"/api/farms/{id}/plans", json={}).status_code, 404)
        finally:
            stranger.close()

    def test_invalid_exclusion_does_not_save(self):
        id = self.farm()
        self.assertEqual(self.client.post(f"/api/farms/{id}/plans", json={"excludedCrops": ["not known"]}).status_code, 422)
        self.assertEqual(self.client.get(f"/api/farms/{id}/plans").json(), [])

    def test_manual_drafts_retained(self):
        id = self.farm()
        draft = {"slot": "alternative_a", "name": "My idea", "crops": ["Wheat", "Pea"], "notes": "Farmer reasoning"}
        self.client.post(f"/api/farms/{id}/strategies", json=draft)
        self.client.post(f"/api/farms/{id}/plans", json={})
        self.assertEqual(self.client.get(f"/api/farms/{id}/strategies").json()[0]["notes"], "Farmer reasoning")

    def test_knowledge_seed_idempotent(self):
        ensure_knowledge(self.db)
        a = self.db.scalar(select(func.count()).select_from(CropRequirement))
        ensure_knowledge(self.db)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(CropRequirement)), a)

    def test_public_library(self):
        r = self.client.get("/api/knowledge")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()["crops"]), 6)
