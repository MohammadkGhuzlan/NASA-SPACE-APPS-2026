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
from backend.recommendation.knowledge import library, resolve, BY_ID, CROPS, ensure_knowledge
from backend.recommendation.schemas import FarmingPlanInput
from backend.recommendation.engine import build_report, calendar_for, rotation_assessment


def fixture(profile=None, features=None, summary_override=None, **kwargs):
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
                        summary_override or summary, features or {"soilInputs": soil, "irrigation": p["irrigation"]}, [])


class PlanningRulesTests(unittest.TestCase):
    def test_aliases_not_substring_guesses(self):
        self.assertEqual(resolve(" Corn "), "maize")
        self.assertIsNone(resolve("cornish pasture"))

    def test_reference_values(self):
        c = BY_ID["dry_bean"]
        self.assertEqual(c["growingDays"], [50, 270])
        self.assertEqual(c["waterMm"], [300, 500])

    def test_curated_ecocrop_subset_has_source_and_quality_disclosure(self):
        k = library()
        self.assertEqual(len(k["crops"]), 13)
        self.assertTrue(k["dataset"]["license"].startswith("CC BY 4.0"))
        self.assertIn("sourceSnapshotSha256", k["dataset"])
        self.assertTrue(all("fao_ecocrop" in c["sourceIds"] for c in CROPS))
        self.assertTrue(any("expert estimates" in x for x in k["limitations"]))
        self.assertNotIn("droughtSensitivity", k["crops"][0])

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
        self.assertEqual(c["harvestEarliest"], "2028-03-01")

    def test_zero_budget_not_missing(self):
        r = fixture(availableSeasonalWaterMm=0)
        self.assertTrue(all(c["status"] in {"water_budget_conflict_review", "conditional_candidate"} for c in r["candidates"]))
        self.assertEqual(r["scenarios"][1]["status"], "insufficient_evidence")
        self.assertEqual(r["status"], "insufficient_evidence")

    def test_exclusions_respected(self):
        r = fixture(excludedCrops=["dry beans", "pea"])
        ids = {c["crop"]["id"] for c in r["candidates"]}
        self.assertNotIn("dry_bean", ids)
        self.assertNotIn("pea", ids)
        self.assertNotIn("Dry bean", r["scenarios"][1]["crops"])
        self.assertNotIn("Pea", r["scenarios"][2]["crops"])

    def test_two_distinct_conditional_alternatives(self):
        r = fixture()
        a, b = r["scenarios"][1:]
        self.assertNotEqual(a["crops"][-3:], b["crops"][-3:])
        self.assertEqual(len(set(a["crops"][-3:])), 3)
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
        self.assertTrue(any(r["code"] == "same_botanical_family" and "Gramineae" in r["message"] for r in risks))
        self.assertTrue(any("usda_nrcs_rotation" in r["sourceIds"] for r in risks))

    def test_no_silent_history_parsing(self):
        r = fixture()
        self.assertTrue(any("chronological crop history" in x for x in r["missingInformation"]))
        self.assertEqual(r["inputs"]["planning"]["previousCrops"], [])

    def test_sequence_water_is_multi_cycle_not_budget(self):
        r = fixture(availableSeasonalWaterMm=700)
        self.assertTrue(any(x["code"] == "water_budget_scope" for x in r["scenarios"][1]["risks"]))

    def test_unknown_duration_blocks_later_calendar(self):
        r = fixture(currentRotation=["Olive", "Wheat"], plantingDate="2027-01-01")
        self.assertIsNone(r["scenarios"][0]["schedule"][1]["harvestEarliest"])

    def test_water_priority_not_fake_score(self):
        r = fixture({"goal": "conserve_water"})
        self.assertEqual(r["priorityApplied"], "conserve_water")
        self.assertTrue(r["scenarios"][1]["crops"][-3:])
        self.assertNotIn("score", r)

    def test_invalid_requests(self):
        from pydantic import ValidationError
        for data in [{"availableSeasonalWaterMm": -1}, {"availableSeasonalWaterMm": float("nan")},
                     {"currentRotation": [""]}, {"plantingDate": "1900-01-01"},
                     {"priority": "maximize_yield"}, {"unknown": 1}]:
            with self.assertRaises(ValidationError):
                FarmingPlanInput(**data)

    def test_snapshot_copies_profile(self):
        r = fixture(operationalLimitations="No potato harvester")
        self.assertEqual(r["inputs"]["planning"]["operationalLimitations"], "No potato harvester")
        self.assertTrue(any(x["code"] == "operational_constraints" for x in r["management"]))

    def test_farmer_reported_ph_and_irrigation_are_review_inputs(self):
        r = fixture(features={"irrigation": "limited", "soilInputs": {
            "ph": {"value": 9.2, "source": "farmer_reported", "depthCm": "0-5"}}})
        wheat = next(c for c in r["candidates"] if c["crop"]["id"] == "wheat")
        self.assertEqual(wheat["screen"]["soilStatus"], "farmer_reported")
        self.assertTrue(any(x["code"] == "possible_soil_ph_mismatch" for x in wheat["risks"]))
        self.assertTrue(any(x["code"] == "irrigation_capacity_unverified" for x in wheat["risks"]))

    def test_proxy_ph_never_screens_out_crop(self):
        r = fixture(features={"irrigation": "rainfed", "soilInputs": {
            "ph": {"value": 12.0, "source": "PROXY_DEMO_ONLY", "depthCm": "0-5"}}})
        wheat = next(c for c in r["candidates"] if c["crop"]["id"] == "wheat")
        self.assertEqual(wheat["screen"]["soilStatus"], "proxy_only")
        self.assertFalse(wheat["screen"]["flagged"])
        self.assertTrue(any(x["code"] == "soil_proxy_not_filter" for x in wheat["risks"]))

    def test_historical_nasa_context_emits_only_reference_flags(self):
        params = ["T2M", "T2M_MIN", "T2M_MAX", "PRECTOTCORR", "GWETTOP", "GWETROOT"]
        monthly = []
        for month in range(1, 13):
            monthly.append({"period": f"2025-{month:02d}", "expectedDays": 31,
                "validDays": {p: 31 for p in params}, "T2M": 20, "T2M_MIN": 0,
                "T2M_MAX": 40, "PRECTOTCORR": 20, "GWETTOP": 0.4, "GWETROOT": 0.3})
        summary = {"availableParameters": params, "monthly": monthly, "annual": [],
            "referencePeriod": "2019–2025", "warnings": [], "location": {},
            "status": "available", "provenance": []}
        r = fixture(plantingDate="2025-01-01", summary_override=summary)
        wheat = next(c for c in r["candidates"] if c["crop"]["id"] == "wheat")
        self.assertTrue(wheat["environmentalContext"]["potentialColdThresholdMismatch"])
        self.assertTrue(wheat["environmentalContext"]["potentialHeatThresholdMismatch"])
        self.assertEqual(wheat["environmentalContext"]["meanMonthlyNASA_GWETROOT"], 0.3)
        self.assertIn("NASA POWER", wheat["environmentalContext"]["note"])
        self.assertNotIn("suitabilityScore", wheat)


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

    def farm(self, **overrides):
        response = self.client.post("/api/farms", json={"name": "Phase 3 isolated test",
            "locationName": "Irbid", "latitude": 32.55696, "longitude": 35.8479,
            "currentCrop": "Wheat", "irrigation": "rainfed", "goal": "soil_health", **overrides})
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
        self.assertEqual(len(r.json()["crops"]), 13)

    def test_farm_profile_ph_is_retained_as_farmer_input(self):
        id = self.farm(soilPh=8.9)
        response = self.client.post(f"/api/farms/{id}/plans", json={"plantingDate": "2027-02-01"})
        self.assertEqual(response.status_code, 201, response.text)
        ph = response.json()["environmentalEvidence"]["soilInputs"]["ph"]
        self.assertEqual(ph["value"], 8.9)
        self.assertEqual(ph["source"], "farmer_profile_unverified")
