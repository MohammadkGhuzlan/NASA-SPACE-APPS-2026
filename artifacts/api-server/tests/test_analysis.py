"""Phase 5 software tests. Synthetic evidence is never a real prediction."""
import copy
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.main import app
from backend.database import engine, get_db
from backend.analysis.model import readiness, model_status, _status
from backend.analysis.features import prepare_features, cached_features, aligned_climate_features
from backend.analysis.service import integrate_report, coverage_diagnostics
from backend.analysis.limits import check_analysis_rate
from backend.environment.constants import LOCATIONS, PARAMETERS, START, END
from backend.environment.power_client import missing_parameters, ensure_environment, parameter_coverage
from backend.environment.power_client import parse_response
from backend.environment.storage import ensure_location
from backend.environment.service import summary_for
from backend.models import EnvironmentalValue, IngestionReport
from backend.admission import admit, PREFIX
from backend.recommendation.schemas import FarmingPlanInput
from backend.recommendation.engine import build_report


def fixture(irrigation="rainfed"):
    farm = SimpleNamespace(id=123, profile={
        "name": "Synthetic software fixture", "latitude": 37.8882, "longitude": -4.7794,
        "currentCrop": "Wheat", "goal": "soil_health", "irrigation": irrigation,
        "agriculturalConstraints": "previously barley", "cropHistory": "barley",
    })
    summary = {
        "referencePeriod": "2019–2025", "status": "available",
        "availableParameters": ["T2M", "PRECTOTCORR"], "monthly": [], "annual": [],
        "location": {"latitude": 37.8882, "longitude": -4.7794}, "warnings": [],
        "provenance": [{"source": "NASA POWER",
                        "metadata": {"timeStandard": "unspecified_in_uploaded_file"}}],
    }
    features = {"soilInputs": {"ph": {
        "value": 7, "source": "PROXY_DEMO_ONLY", "depthCm": "0-5", "unit": "pH"
    }}}
    return farm, summary, features


class AnalysisUnitTests(unittest.TestCase):
    def test_prepared_cache_invalidated_by_farmer_and_source_changes(self):
        farm, summary, features = fixture()
        planning = FarmingPlanInput()
        a = cached_features(farm, planning, summary, features, model_status()["contract"])
        a["soilInputs"]["ph"]["value"] = -100
        b = cached_features(farm, planning, summary, features, model_status()["contract"])
        self.assertEqual(b["soilInputs"]["ph"]["value"], 7)
        features["soilInputs"]["ph"]["value"] = 8.5
        c = cached_features(farm, planning, summary, features, model_status()["contract"])
        self.assertEqual(c["soilInputs"]["ph"]["value"], 8.5)

    def test_actual_phase4_climate_transform_is_reused_not_reimplemented(self):
        payload = {"synthetic": "software fixture; deliberately not complete climate data"}
        with patch("backend.machine_learning.environment.power_features", return_value={"synthetic": True}) as transform:
            self.assertEqual(aligned_climate_features(payload, model_status()["contract"]), {"synthetic": True})
            transform.assert_called_once_with(payload, period=[2001, 2020])
        with self.assertRaises(ValueError):
            aligned_climate_features(payload, {})

    def test_real_readiness_is_rejected_not_ready(self):
        s = model_status()
        self.assertEqual(s["state"], "insufficiently_validated")
        self.assertFalse(s["predictionsEnabled"])
        self.assertEqual(s["contract"]["period"], [2001, 2020])
        self.assertEqual(s["target"]["unit"], "Index")
        self.assertNotIn("prediction", s)

    def test_missing_model(self):
        s = model_status()
        r = readiness(s["contract"], {}, s["target"])
        self.assertEqual(r["state"], "not_installed")
        self.assertFalse(r["predictionsEnabled"])

    def test_malformed_contract(self):
        for contract in [{}, None, [], {"version": "something"}]:
            with self.subTest(contract=contract):
                self.assertEqual(readiness(contract, {}, {})["state"], "incompatible")

    def test_units_mismatch(self):
        contract = model_status()["contract"]
        contract["units"] = {}
        self.assertEqual(readiness(contract, {}, {})["state"], "incompatible")

    def test_accepted_research_does_not_activate(self):
        s = model_status()
        r = readiness(s["contract"], {"outcome": "accepted", "deployable_model_saved": True}, s["target"])
        self.assertFalse(r["predictionsEnabled"])
        self.assertIn("stage_b_operator_review_required", r["reasons"])

    def test_temporarily_unavailable(self):
        self.assertEqual(readiness(model_status()["contract"], [], {})["state"],
                         "temporarily_unavailable")

    def test_metadata_corrupt_no_file_paths_disclosed(self):
        with tempfile.TemporaryDirectory() as tmp, patch("backend.analysis.model.EVIDENCE", Path(tmp)):
            _status.cache_clear()
            result = model_status()
            self.assertEqual(result["state"], "temporarily_unavailable")
            self.assertNotIn(tmp, json.dumps(result))
        _status.cache_clear()

    def test_cached_readiness_not_mutable(self):
        s = model_status()
        s["contract"]["period"][0] = -5
        self.assertEqual(model_status()["contract"]["period"], [2001, 2020])

    def test_no_fabricated_model_feature_vector(self):
        farm, summary, features = fixture()
        p = prepare_features(farm, FarmingPlanInput(), summary, features, model_status()["contract"])
        self.assertIsNone(p["modelFeatures"])
        self.assertFalse(p["compatible"])
        self.assertIn("reference_period_mismatch", p["unavailableReasons"])
        self.assertIn("daily_time_standard_unverified_or_mixed", p["unavailableReasons"])
        self.assertEqual(p["coordinates"]["latitude"], 37.8882)
        self.assertFalse(p["coordinates"]["farmBoundaryAggregated"])

    def test_soil_measurement_not_relabelled_as_source_aggregate(self):
        farm, summary, features = fixture()
        features["soilInputs"]["ph"]["source"] = "laboratory_confirmed"
        p = prepare_features(farm, FarmingPlanInput(), summary, features, model_status()["contract"])
        self.assertIn("soil_source_or_spatial_aggregation_incompatible", p["unavailableReasons"])
        self.assertEqual(p["soilInputs"]["ph"]["source"], "laboratory_confirmed")

    def test_missing_soil_and_climate(self):
        farm, summary, _ = fixture()
        summary["status"] = "unavailable"
        p = prepare_features(farm, FarmingPlanInput(), summary, {}, model_status()["contract"])
        self.assertIn("soil_features_missing", p["unavailableReasons"])
        self.assertIn("environmental_data_incomplete", p["unavailableReasons"])

    def test_management_not_inferred_from_irrigation(self):
        for irrigation, reason in [("rainfed", "low_input_management_not_confirmed"),
                                    ("fully_irrigated", "management_scenario_not_supported")]:
            farm, summary, features = fixture(irrigation)
            p = prepare_features(farm, FarmingPlanInput(), summary, features, model_status()["contract"])
            self.assertIn(reason, p["unavailableReasons"])

    def test_coverage_checks_never_use_city_distance(self):
        farm, summary, features = fixture()
        p = prepare_features(farm, FarmingPlanInput(), summary, features, model_status()["contract"])
        for crop in ["wheat", "rice", "chickpea"]:
            r = coverage_diagnostics(crop, p, model_status())
            self.assertFalse(r["available"])
            self.assertEqual(r["status"], "insufficient_evidence")
            self.assertNotIn("prediction", r)
            self.assertNotIn("confidence", r)
            if crop == "rice":
                self.assertIsNone(r["modelCrop"])

    def test_reference_planner_not_replaced_or_mutated(self):
        farm, summary, features = fixture()
        planning = FarmingPlanInput(previousCrops=["Barley"], currentRotation=["Wheat", "Pea"])
        report = build_report(farm, planning, summary, features, [])
        before = copy.deepcopy(report)
        after = integrate_report(farm, planning, summary, features, report)
        self.assertEqual(report, before)
        after.pop("aiIntegration")
        self.assertEqual(before, after)

    def test_history_never_parsed_from_constraints(self):
        farm, summary, features = fixture()
        p = prepare_features(farm, FarmingPlanInput(), summary, features, model_status()["contract"])
        self.assertEqual(p["planningInputs"]["previousCrops"], [])
        self.assertEqual(p["farmerProfile"]["agriculturalConstraints"], "previously barley")

    def test_coverage_requires_every_parameter_and_day(self):
        days = (END - START).days + 1
        self.assertEqual(missing_parameters({p: days for p in PARAMETERS}), [])
        coverage = {p: days for p in PARAMETERS}
        coverage["GWETROOT"] = days - 1
        self.assertEqual(missing_parameters(coverage), ["GWETROOT"])

    def test_malformed_nasa_payload_rejected(self):
        for payload in [[], {}, {"header": [], "properties": {}},
                        {"header": {}, "parameters": {}, "properties": {"parameter": []}}]:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                parse_response(payload, ["T2M"], fixture()[0], "https://power.larc.nasa.gov/")

    def test_invalid_model_metadata_never_deserializes(self):
        with tempfile.TemporaryDirectory() as tmp, patch("backend.analysis.model.EVIDENCE", Path(tmp)):
            (Path(tmp) / "feature-contract.json").write_text("not valid JSON")
            _status.cache_clear()
            with patch("joblib.load", side_effect=AssertionError("Stage A must not deserialize")):
                self.assertFalse(model_status()["predictionsEnabled"])
        _status.cache_clear()


class AnalysisApiTests(unittest.TestCase):
    """Rollback each test; never migrate, delete, or persist user records."""
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
        r = self.client.post("/api/farms", json={
            "name": "Phase 5 rollback test", "latitude": 32.55696, "longitude": 35.8479,
            "locationName": "Irbid", "currentCrop": "Wheat",
            "irrigation": "rainfed", "goal": "soil_health", **overrides})
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()["id"]

    def test_readiness_endpoint(self):
        r = self.client.get("/api/analysis/model-status")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.json()["predictionsEnabled"])
        self.assertNotIn("directory", r.json())

    def test_shared_report_limit_survives_owner_rotation(self):
        # A second session facade is not a second process-local counter: every
        # permit is read from the shared database, under an advisory lock.
        for n in range(24):
            check_analysis_rate(f"synthetic-owner-{n}", self.db)
        with self.assertRaises(HTTPException) as caught:
            check_analysis_rate("another-new-browser-owner", self.db)
        self.assertEqual(caught.exception.status_code, 429)

    def test_shared_owner_and_nasa_budgets(self):
        for _ in range(6):
            check_analysis_rate("synthetic-one-owner", self.db)
        with self.assertRaises(HTTPException):
            check_analysis_rate("synthetic-one-owner", self.db)
        check_analysis_rate("different-owner", self.db)
        for _ in range(12):
            admit(self.db, "nasa", 12)
        with self.assertRaises(HTTPException):
            admit(self.db, "nasa", 12)

    def test_admission_rows_are_private_and_only_technical_rows_expire(self):
        old = datetime.now(timezone.utc) - timedelta(days=2)
        audit = IngestionReport(source="Synthetic preserved import audit", status="completed",
                                started_at=old, report={"nonSensitiveFixture": True})
        self.db.add_all([audit, IngestionReport(source=PREFIX+"analysis", status="internal_admission",
                        started_at=old, report={"scope": "old-synthetic-scope"})])
        self.db.commit()
        kept_id = audit.id
        check_analysis_rate("synthetic-owner", self.db)
        self.assertIsNotNone(self.db.get(IngestionReport, kept_id))
        response = self.client.get("/api/data/status")
        self.assertNotIn(PREFIX, response.text)
        self.assertNotIn("synthetic-owner", response.text)

    def test_other_products_cannot_hide_missing_nasa_dates(self):
        loc = ensure_location(self.db, 38.12345, -4.54321)
        count = (END-START).days+1
        # More than the required number of rows, but only one date and no
        # expected NASA POWER product. This must still be incomplete.
        self.db.add_all([EnvironmentalValue(
            location_key=loc.key, date=START, parameter="T2M", value=None, unit="C",
            source="Synthetic software fixture", product=f"OTHER_{n}", source_url="https://example.org/test",
            classification="software_fixture", quality="missing", metadata_json={}) for n in range(count)])
        self.db.flush()
        self.assertEqual(parameter_coverage(self.db, loc.key).get("T2M", 0), 0)
        self.db.add(EnvironmentalValue(
            location_key=loc.key, date=START, parameter="T2M", value=None, unit="C",
            source="NASA POWER", product="POWER_DAILY", source_url="https://power.larc.nasa.gov/",
            classification="software_fixture", quality="missing_fill", metadata_json={}))
        self.db.flush()
        self.assertEqual(parameter_coverage(self.db, loc.key)["T2M"], 1)
        self.assertIn("T2M", missing_parameters(parameter_coverage(self.db, loc.key)))

    def test_partial_utc_retrieval_does_not_relabel_imported_cache(self):
        loc = ensure_location(self.db, 38.12346, -4.54322)
        self.db.add(EnvironmentalValue(
            location_key=loc.key, date=START, parameter="T2M", value=15, unit="C",
            source="NASA POWER", product="POWER_DAILY", source_url="https://power.larc.nasa.gov/",
            classification="software_fixture", quality="valid",
            metadata_json={"timeStandard": "unspecified_in_uploaded_file"}))
        self.db.commit()
        def request(client, lat, lon, group):
            params = {p: {"20190101": 0.5 if p.startswith("GWET") else 15} for p in group}
            return {"header": {"time_standard": "UTC"}, "parameters": {
                p: {"units": PARAMETERS[p][0]} for p in group},
                "properties": {"parameter": params}}, "https://power.larc.nasa.gov/"
        with patch("backend.environment.power_client.request_group", side_effect=request):
            loc = ensure_environment(self.db, loc.latitude, loc.longitude)
        self.assertNotIn("timeStandard", loc.metadata_json)
        self.assertEqual(loc.metadata_json["requestTimeStandard"], "UTC")
        summary = summary_for(self.db, loc)
        self.assertTrue(any("time standard" in w for w in summary["warnings"]))
        self.assertIn("unspecified_in_uploaded_file", [
            p["metadata"]["timeStandard"] for p in summary["provenance"]])

    def test_saved_snapshot_and_owner_enforcement(self):
        farm_id = self.farm()
        r = self.client.post(f"/api/farms/{farm_id}/plans", json={"previousCrops": ["Barley"]})
        self.assertEqual(r.status_code, 201, r.text)
        data = r.json()
        self.assertIn("aiIntegration", data)
        self.assertEqual(len(data["scenarios"]), 3)
        self.assertTrue(all(not c["available"] for c in data["aiIntegration"]["coverage"]))
        self.assertEqual(data, self.client.get(f"/api/farms/{farm_id}/plans/{data['id']}").json())
        stranger = TestClient(app)
        try:
            self.assertEqual(stranger.post(f"/api/farms/{farm_id}/plans", json={}).status_code, 404)
            self.assertEqual(stranger.get(f"/api/farms/{farm_id}/plans/{data['id']}").status_code, 404)
        finally:
            stranger.close()

    def test_no_public_model_paths_or_verified_features(self):
        farm_id = self.farm()
        for body in [{"modelPath": "arbitrary.joblib"}, {"source_quality": "verified_source_estimates"},
                     {"features": {"ph": 7}}, {"priority": "invalid"}, {"availableSeasonalWaterMm": -1}]:
            self.assertEqual(self.client.post(f"/api/farms/{farm_id}/plans", json=body).status_code, 422)

    def test_four_study_regions_use_their_own_cached_data(self):
        with patch("backend.environment.power_client.request_group",
                   side_effect=AssertionError("Complete study cache must not be downloaded")):
            for _, (_, lat, lon) in LOCATIONS.items():
                location = ensure_environment(self.db, lat, lon)
                self.assertAlmostEqual(location.latitude, lat)
                self.assertAlmostEqual(location.longitude, lon)

    def test_unseen_cordoba_failure_never_substitutes_study(self):
        farm_id = self.farm(latitude=37.8882, longitude=-4.7794, locationName="Córdoba test point")
        with patch("backend.environment.power_client.request_group", side_effect=ValueError("simulated NASA outage")):
            r = self.client.post(f"/api/farms/{farm_id}/plans", json={})
        self.assertEqual(r.status_code, 201, r.text)
        p = r.json()["aiIntegration"]["featurePreparation"]
        self.assertEqual(p["environmentLocation"]["latitude"], 37.8882)
        self.assertEqual(p["environmentLocation"]["longitude"], -4.7794)
        self.assertEqual(p["environmentStatus"], "unavailable")
        self.assertIsNone(p["modelFeatures"])
        public = self.client.get("/api/data/status").json()
        api_reports = [r for r in public["reports"] if r["source"].startswith("NASA POWER API")]
        self.assertTrue(api_reports)
        self.assertNotIn("37.88820", json.dumps(api_reports))
        self.assertTrue(all("latitude" not in r["report"] and "longitude" not in r["report"]
                            for r in api_reports))

    def test_same_location_different_profiles_affect_reference_plans(self):
        a = self.farm(soilPh=5.5, goal="soil_health")
        b = self.farm(soilPh=9.5, goal="conserve_water", irrigation="fully_irrigated", currentCrop="Maize")
        r1 = self.client.post(f"/api/farms/{a}/plans", json={
            "previousCrops": ["Pea"], "plantingDate": "2027-02-01"}).json()
        r2 = self.client.post(f"/api/farms/{b}/plans", json={
            "previousCrops": ["Wheat"], "plantingDate": "2027-02-01",
            "availableSeasonalWaterMm": 0}).json()
        self.assertNotEqual(r1["priorityApplied"], r2["priorityApplied"])
        self.assertNotEqual(r1["scenarios"], r2["scenarios"])
        self.assertEqual(r1["environmentalEvidence"]["soilInputs"]["ph"]["value"], 5.5)
        self.assertEqual(r2["environmentalEvidence"]["soilInputs"]["ph"]["value"], 9.5)
        self.assertFalse(r1["aiIntegration"]["model"]["predictionsEnabled"])
        self.assertFalse(r2["aiIntegration"]["model"]["predictionsEnabled"])

    def test_excessive_reports_limited_before_nasa(self):
        farm_id = self.farm()
        with patch("backend.recommendation.routes.check_analysis_rate",
                   side_effect=HTTPException(429, "Test rate limit")), patch(
                       "backend.recommendation.routes.ensure_environment") as nasa:
            self.assertEqual(self.client.post(f"/api/farms/{farm_id}/plans", json={}).status_code, 429)
            nasa.assert_not_called()

    def test_invalid_coordinates_rejected(self):
        r = self.client.get("/api/environment/summary?latitude=nan&longitude=-4.7794")
        self.assertEqual(r.status_code, 422)


if __name__ == "__main__":
    unittest.main()
