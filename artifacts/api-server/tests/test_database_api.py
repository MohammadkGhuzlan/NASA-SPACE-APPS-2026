"""Integration tests use the development schema inside a rolled-back transaction.

No migrations, production access, or deletion of user data. NASA calls are mocked
where needed; one real new-location retrieval is documented in the delivery report.
"""
import copy
import unittest
from unittest.mock import patch
from datetime import date
from fastapi.testclient import TestClient
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from backend.main import app
from backend.database import engine, get_db
from backend.models import EnvironmentalValue, EnvironmentalLocation, SoilEstimate, Farm
from backend.environment.constants import LOCATIONS, location_key
from backend.environment.importer import import_bundle, read_csv
from backend.environment.storage import store_values
from backend.environment.power_client import ensure_environment


class DatabaseApiTests(unittest.TestCase):
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
        return self.client.post("/api/farms", json={
            "name": "Automated test field", "locationName": "Irbid", "latitude": 32.55696, "longitude": 35.8479,
            "currentCrop": "Wheat", "irrigation": "rainfed", "goal": "soil_health",
        }).json()

    def test_study_locations_match_uploaded_reference(self):
        rows = self.client.get("/api/case-studies").json()
        self.assertEqual(len(rows), 4)
        for r, (name, lat, lon) in zip(rows, LOCATIONS.values()):
            self.assertEqual((r["latitude"], r["longitude"]), (lat, lon))

    def test_summary_matches_database_daily_values(self):
        response = self.client.get("/api/environment/summary?latitude=32.55696&longitude=35.8479")
        self.assertEqual(response.status_code, 200)
        summary = response.json()
        values = self.db.scalars(select(EnvironmentalValue).where(
            EnvironmentalValue.location_key == "32.55696,35.84790", EnvironmentalValue.parameter == "PRECTOTCORR",
            EnvironmentalValue.date >= date(2025, 1, 1), EnvironmentalValue.date <= date(2025, 1, 31))).all()
        self.assertAlmostEqual(summary["monthly"][-12]["PRECTOTCORR"], sum(v.value for v in values))
        self.assertEqual(summary["monthly"][-12]["validDays"]["PRECTOTCORR"], 31)
        self.assertEqual(len(summary["provenance"]), 7)

    def test_history_units_and_dates(self):
        r = self.client.get("/api/environment/history?latitude=32.55696&longitude=35.8479&year=2020").json()
        self.assertEqual(len(r["daily"]), 366)
        self.assertEqual(r["daily"][0]["date"], "2020-01-01")
        self.assertEqual(r["units"]["GWETTOP"], "1")
        self.assertEqual(r["units"]["PRECTOTCORR"], "mm/day")

    def test_soil_proxy_coordinates_and_distance_flag(self):
        r = self.client.get("/api/environment/soil-properties?latitude=24.2249&longitude=55.7452").json()
        e = r["estimate"]
        self.assertEqual(e["classification"], "PROXY_DEMO_ONLY")
        self.assertEqual(e["originalLatitude"], 24.2249)
        self.assertNotEqual(e["sampleLatitude"], e["originalLatitude"])
        self.assertEqual(e["offsetKm"], 7.073)
        self.assertAlmostEqual(e["provenance"]["calculatedOffsetKm"], 6.451, places=2)
        self.assertEqual(e["provenance"]["quality"], "distance_discrepancy")

    def test_soil_does_not_use_nearest_city(self):
        with patch("backend.environment.power_client.request_group", side_effect=AssertionError("Soil must not request NASA")):
            r = self.client.get("/api/environment/soil-properties?latitude=32.557&longitude=35.848").json()
        self.assertEqual(r["status"], "unavailable")
        self.assertIsNone(r["estimate"])

    def test_import_is_forbidden_to_public_session(self):
        self.assertEqual(self.client.post("/api/data/import").status_code, 403)

    def test_invalid_coordinate_and_year_rejected(self):
        self.assertEqual(self.client.get("/api/environment/summary?latitude=91&longitude=0").status_code, 422)
        self.assertEqual(self.client.get("/api/environment/history?latitude=32.55696&longitude=35.8479&year=1900").status_code, 422)
        self.assertEqual(self.client.get("/api/environment/summary?latitude=nan&longitude=0").status_code, 422)

    def test_measurement_persists_and_other_owner_blocked(self):
        farm = self.farm()
        # Optional profile context survives editing and explicit clearing.
        profile = {**farm, "waterResources": "Rainwater tank", "agriculturalConstraints": "Heavy equipment unavailable"}
        updated = self.client.put(f"/api/farms/{farm['id']}", json=profile)
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["waterResources"], "Rainwater tank")
        profile["waterResources"] = ""
        self.assertEqual(self.client.put(f"/api/farms/{farm['id']}", json=profile).json()["waterResources"], "")
        data = {"parameter": "ph", "value": 7.2, "unit": "pH", "depthTopCm": 0, "depthBottomCm": 5,
                "measuredOn": "2025-02-01", "source": "laboratory_confirmed", "notes": "Test lab report"}
        saved = self.client.post(f"/api/farms/{farm['id']}/measurements", json=data)
        self.assertEqual(saved.status_code, 201)
        result = self.client.get(f"/api/farms/{farm['id']}/measurements").json()[0]
        self.assertEqual(result["value"], 7.2)
        self.assertIn("not independently verified", result["verification"])
        with TestClient(app) as other:
            self.assertEqual(other.get(f"/api/farms/{farm['id']}/measurements").status_code, 404)
            self.assertEqual(other.post(f"/api/farms/{farm['id']}/measurements", json=data).status_code, 404)
        self.assertEqual(self.client.get(f"/api/farms/{farm['id']}").json()["name"], farm["name"])

    def test_feature_override_requires_same_variable_depth_unit(self):
        farm = self.farm()
        path = f"/api/farms/{farm['id']}"
        data = {"parameter": "ph", "value": 6.2, "unit": "pH", "depthTopCm": 0, "depthBottomCm": 10,
                "measuredOn": "2025-02-01", "source": "farmer_reported"}
        self.client.post(path+"/measurements", json=data)
        inputs = self.client.get(path+"/features").json()["soilInputs"]
        self.assertEqual(inputs["ph"]["source"], "PROXY_DEMO_ONLY")
        data["depthBottomCm"] = 5
        self.client.post(path+"/measurements", json=data)
        result = self.client.get(path+"/features").json()
        self.assertEqual(result["soilInputs"]["ph"]["source"], "farmer_reported")
        self.assertEqual(result["soilInputs"]["ph"]["value"], 6.2)
        self.assertEqual(result["soilInputs"]["clay_pct"]["source"], "PROXY_DEMO_ONLY")
        self.assertIsNone(result["labels"])
        # Original proxy was never overwritten.
        self.assertEqual(self.client.get("/api/environment/soil-properties?latitude=32.55696&longitude=35.8479").json()["estimate"]["properties"]["ph"]["value"], 7.9)

    def test_composition_measurements_total_validation(self):
        farm = self.farm()
        path = f"/api/farms/{farm['id']}/measurements"
        data = {"parameter": "clay_pct", "value": 60, "unit": "%", "measuredOn": "2025-02-01", "source": "farmer_reported"}
        self.assertEqual(self.client.post(path, json=data).status_code, 201)
        self.assertEqual(self.client.post(path, json={**data, "parameter": "sand_pct", "value": 30}).status_code, 201)
        self.assertEqual(self.client.post(path, json={**data, "parameter": "silt_pct", "value": 30}).status_code, 422)

    def test_immutable_conflict_is_reported(self):
        row = self.db.scalar(select(EnvironmentalValue).where(EnvironmentalValue.location_key == "32.55696,35.84790"))
        before = row.value
        record = {k: getattr(row, k) for k in ("location_key", "date", "parameter", "value", "unit", "source", "product", "source_url", "classification", "quality", "metadata_json", "retrieved_at")}
        record["value"] = before + .1 if before is not None else 1
        inserted, skipped, conflicts = store_values(self.db, [record])
        self.assertEqual((inserted, conflicts), (0, 1))
        self.db.refresh(row)
        self.assertEqual(row.value, before)

    def test_cached_study_does_not_call_nasa(self):
        with patch("backend.environment.power_client.request_group", side_effect=AssertionError("Cached location called upstream")):
            loc = ensure_environment(self.db, 32.55696, 35.8479)
        self.assertEqual(loc.study_id, "irbid")

    def test_new_point_does_not_use_irbid(self):
        with patch("backend.environment.power_client.request_group", side_effect=ValueError("NASA rejected test point")) as request:
            loc = ensure_environment(self.db, 32.55711, 35.84822)
        self.assertIsNone(loc.study_id)
        self.assertEqual(request.call_count, 2)
        self.assertIn("rejected", loc.last_error)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(EnvironmentalValue).where(EnvironmentalValue.location_key == loc.key)), 0)
        with patch("backend.environment.power_client.request_group", side_effect=AssertionError("Negative cache ignored")):
            ensure_environment(self.db, 32.55711, 35.84822)

    def test_comparison_has_four_real_summaries(self):
        r = self.client.get("/api/environment/compare").json()
        self.assertEqual(len(r), 4)
        self.assertTrue(all(len(item["summary"]["annual"]) == 7 for item in r))
        self.assertNotEqual(r[0]["summary"]["annual"][-1]["PRECTOTCORR"], r[1]["summary"]["annual"][-1]["PRECTOTCORR"])

    def test_repeated_import_has_no_new_values(self):
        before = self.db.scalar(select(func.count()).select_from(EnvironmentalValue))
        with patch("backend.environment.importer.SessionLocal", return_value=self.db):
            r = import_bundle()
        self.assertEqual(r["status"], "completed")
        by_name = {f["fileName"]: f for f in r["files"]}
        self.assertEqual(by_name["nasa_daily.csv"]["skippedRows"], 10228)
        self.assertEqual(by_name["nasa_soil_moisture_daily.csv"]["skippedRows"], 10228)
        self.assertEqual(by_name["soilgrids_0_5cm_aligned.csv"]["skippedRows"], 4)
        # The importer closes its own session; recreate bound savepoint session.
        self.db = Session(bind=self.connection, join_transaction_mode="create_savepoint")
        self.assertEqual(self.db.scalar(select(func.count()).select_from(EnvironmentalValue)), before)

    def test_import_detects_duplicate_invalid_date_and_classification(self):
        def changed(path, required):
            headers, rows = read_csv(path, required)
            if path.name == "nasa_daily.csv":
                rows = [rows[0], rows[0], {**rows[1], "date": "2019-02-30"}, {**rows[2], "T2M": "infinity"}]
            if path.name == "nasa_soil_moisture_daily.csv":
                rows = [{**rows[0], "data_classification": "SMAP"}]
            return headers, rows
        with patch("backend.environment.importer.read_csv", side_effect=changed), patch("backend.environment.importer.SessionLocal", return_value=self.db):
            r = import_bundle()
        climate, monthly, wetness, soil = r["files"]
        self.assertEqual(climate["invalidRows"], 3)
        self.assertEqual(wetness["invalidRows"], 1)
        self.assertEqual(r["status"], "partial")
        self.db = Session(bind=self.connection, join_transaction_mode="create_savepoint")


if __name__ == "__main__":
    unittest.main()
