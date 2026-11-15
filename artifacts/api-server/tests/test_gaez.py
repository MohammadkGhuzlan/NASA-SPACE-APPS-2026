"""GAEZ software fixtures are synthetic. Real-source checks are explicitly separate."""
from copy import deepcopy
import json
import math
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np
import rasterio
from rasterio.io import MemoryFile
from rasterio.transform import from_origin
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from backend.database import engine, get_db
from backend.main import app
from backend.gaez.catalog import (ROOT, DATASET, CROPS, SCENARIOS, CLASSES, BASE,
                                  SourceUnavailable, read_manifest, catalog_status)
from backend.gaez.sampling import assess, read_cell, verified_file
from backend.gaez.service import integrate_evidence, codes_for
from backend.gaez.ingest import validate_raster
from backend.recommendation.engine import build_report
from backend.recommendation.schemas import FarmingPlanInput
from backend.analysis.model import model_status
from backend.machine_learning.common import sha256


def memory_raster(values, *, crs="EPSG:4326", transform=None):
    values = np.array(values, dtype="uint8")
    mem = MemoryFile()
    src = mem.open(driver="GTiff", width=values.shape[1], height=values.shape[0],
                   count=1, dtype="uint8", crs=crs, nodata=0,
                   transform=transform or from_origin(-1, 1, 1, 1))
    src.write(values, 1)
    return mem, src


class SamplingSoftwareTests(unittest.TestCase):
    def test_exact_cell_not_neighbor_or_interpolation(self):
        m, s = memory_raster([[1, 6], [8, 3]])
        with m, s:
            r = read_cell(s, .5, .5)
            self.assertEqual((r["rawValue"], r["sampling"]["row"], r["sampling"]["column"]), (6, 0, 1))
            self.assertEqual(r["category"], "SI >10 : Marginal")
            self.assertEqual(r["sampling"]["cellBounds"], [0, 0, 1, 1])

    def test_real_crs_transformation(self):
        m, s = memory_raster([[2]], crs="EPSG:3857",
                             transform=from_origin(0, 120000, 120000, 120000))
        with m, s:
            r = read_cell(s, .5, .5)
            self.assertEqual(r["rawValue"], 2)
            self.assertEqual(r["sampling"]["cellBoundsCrs"], "EPSG:3857")
            self.assertGreater(r["sampling"]["cellCenterLatitude"], 0)

    def test_nodata_remains_missing(self):
        m, s = memory_raster([[0]])
        with m, s:
            r = read_cell(s, .5, -.5)
            self.assertEqual(r["status"], "nodata")
            self.assertIsNone(r["rawValue"])
            self.assertIsNone(r["category"])

    def test_water_is_not_agricultural_success(self):
        m, s = memory_raster([[9]])
        with m, s:
            r = read_cell(s, .5, -.5)
            self.assertEqual(r["status"], "not_land")
            self.assertEqual(r["category"], "Water")

    def test_outside_layer_never_clamps(self):
        m, s = memory_raster([[1]])
        with m, s:
            r = read_cell(s, -5, 5)
            self.assertEqual(r["status"], "outside_coverage")
            self.assertIsNone(r["rawValue"])

    def test_unknown_category_refused(self):
        m, s = memory_raster([[255]])
        with m, s, self.assertRaises(SourceUnavailable):
            read_cell(s, .5, -.5)

    def test_invalid_coordinates(self):
        for lat, lon in [(91, 0), (0, -181), (math.nan, 0), (0, math.inf)]:
            with self.assertRaises(ValueError):
                assess(lat, lon, "WHE", "LRLM")

    def test_unsupported_crop_period_version_scenario(self):
        for kwargs in [dict(crop_code="FAKE", scenario="LRLM"),
                       dict(crop_code="WHE", scenario="FAKE"),
                       dict(crop_code="WHE", scenario="LRLM", period="2019-2025"),
                       dict(crop_code="WHE", scenario="LRLM", version="v4")]:
            r = assess(0, 0, **kwargs)
            self.assertEqual(r["status"], "unsupported")
            self.assertIsNone(r["rawValue"])

    def test_missing_cache_does_not_make_up_measurements(self):
        with tempfile.TemporaryDirectory() as root:
            r = assess(37.88, -4.77, "WHE", "LRLM", root=root)
        self.assertEqual(r["status"], "unavailable")
        self.assertIsNone(r["rawValue"])

    def test_changed_raster_checksum_refused(self):
        with tempfile.TemporaryDirectory() as root:
            p = Path(root) / "asset.tif"
            p.write_bytes(b"software fixture")
            with self.assertRaises(SourceUnavailable):
                verified_file(str(p), p.stat().st_size, p.stat().st_mtime_ns, "0" * 64)

    def test_bad_metadata_fails_closed(self):
        with tempfile.TemporaryDirectory() as root:
            (Path(root) / "manifest.json").write_text('{"dataset":{"variable":"RES05-SXX"}}')
            with self.assertRaises(SourceUnavailable):
                read_manifest(root)

    def test_rice_mapping_explicit_and_official_codes(self):
        self.assertEqual(codes_for("Rice"), ["RCD", "RCW"])
        self.assertEqual(codes_for("Wetland rice"), ["RCW"])
        self.assertEqual(codes_for("Dryland rice"), ["RCD"])
        self.assertEqual(codes_for("corn"), ["MZE"])
        self.assertEqual(codes_for("unknown crop"), [])
        self.assertEqual(codes_for("gram"), [])
        self.assertEqual(CROPS["CHK"], "Chickpea")
        self.assertEqual(len(SCENARIOS), 4)

    def test_scale_is_classes_not_percent(self):
        self.assertEqual(DATASET["variable"], "RES05-SIX")
        self.assertIn("not a probability", DATASET["unit"])
        self.assertEqual(CLASSES[8], "Not suitable")
        self.assertEqual(DATASET["noData"], 0)


class LiveSourceTests(unittest.TestCase):
    """Actually acquired official raster tests: fail if assets were not acquired."""
    @classmethod
    def setUpClass(cls):
        cls.manifest = read_manifest()

    def test_authentic_catalog_all_twenty_eight_assets(self):
        self.assertEqual(len(self.manifest["assets"]), 28)
        self.assertEqual(catalog_status()["cachedLayers"], 28)
        for a in self.manifest["assets"]:
            self.assertEqual(a["catalogRow"]["CROP"], a["cropCode"])
            self.assertEqual(a["catalogRow"]["INPUT"], a["scenario"])
            self.assertEqual(a["url"], BASE + a["file"])
            self.assertEqual(sha256(ROOT / a["file"]), a["sha256"])

    def test_headers_units_and_classes_match_actual_sources(self):
        for a in self.manifest["assets"]:
            validate_raster(ROOT / a["file"])
        self.assertEqual(self.manifest["classes"], {str(k): v for k, v in CLASSES.items()})

    def test_five_locations_all_crops_scenarios_independently_repeatable(self):
        locations = {"Irbid": (32.55696, 35.84790), "Al Ain": (24.2249, 55.7452),
                     "Colusa": (39.2146, -122.0094), "Stuttgart": (34.5004, -91.5526),
                     "Córdoba": (37.8882, -4.7794)}
        proof = []
        for name, (lat, lon) in locations.items():
            for a in self.manifest["assets"]:
                r = assess(lat, lon, a["cropCode"], a["scenario"], manifest=self.manifest)
                # Independent extraction: rasterio.sample (not service window/index code).
                with rasterio.open(ROOT / a["file"]) as src:
                    value = next(src.sample([(lon, lat)], masked=True))[0]
                    independent = None if bool(getattr(value, "mask", False)) else int(value)
                self.assertEqual(r["rawValue"], independent)
                self.assertEqual(r["sampling"]["latitude"], lat)
                self.assertEqual(r["sampling"]["longitude"], lon)
                self.assertEqual(r["category"], CLASSES[independent] if independent is not None else None)
                proof.append({"location": name, "latitude": lat, "longitude": lon,
                              "crop": a["cropCode"], "scenario": a["scenario"],
                              "status": r["status"], "value": r["rawValue"],
                              "category": r["category"], "datasetId": r["datasetId"],
                              "sha256": r["sha256"], "sampling": r["sampling"]})
        (ROOT / "real-lookups.json").write_text(json.dumps(proof, indent=2))
        self.assertEqual(len(proof), 140)

    def test_repeated_lookup_reuses_local_cache_without_network(self):
        a = self.manifest["assets"][0]
        before = (ROOT / a["file"]).stat()
        with patch("httpx.Client.request", side_effect=AssertionError("No live download allowed")):
            x = assess(37.8882, -4.7794, a["cropCode"], a["scenario"], manifest=self.manifest)
            y = assess(37.8882, -4.7794, a["cropCode"], a["scenario"], manifest=self.manifest)
        self.assertEqual(x, y)
        self.assertEqual(before.st_mtime_ns, (ROOT / a["file"]).stat().st_mtime_ns)

    def test_authentic_nodata_pixel_is_not_a_successful_assessment(self):
        a = self.manifest["assets"][0]
        with rasterio.open(ROOT / a["file"]) as src:
            row, col = np.argwhere(src.read(1) == 0)[0]
            lon, lat = src.xy(int(row), int(col))
        r = assess(lat, lon, a["cropCode"], a["scenario"], manifest=self.manifest)
        self.assertEqual(r["status"], "nodata")
        self.assertIsNone(r["rawValue"])


class PlannerEvidenceTests(unittest.TestCase):
    def fixture(self, **changes):
        farm = SimpleNamespace(id=0, profile={"name": "Synthetic test only",
            "latitude": 34.5004, "longitude": -91.5526, "currentCrop": "Rice",
            "cropHistory": "Soybean; Rice", "irrigation": "limited",
            "goal": "conserve_water", "farmSize": 15, **changes})
        p = FarmingPlanInput(currentRotation=["Rice"], previousCrops=["Soybean", "Rice"])
        s = {"referencePeriod": "2019-01-01 to 2025-12-31",
             "availableParameters": ["T2M"], "annual": [], "monthly": [], "warnings": []}
        f = {"soilInputs": {}, "irrigation": "limited"}
        base = build_report(farm, p, s, f, [])
        return farm, p, s, f, base

    def test_arkansas_preserves_three_rotations_and_adds_published_evidence(self):
        farm, p, s, f, base = self.fixture()
        before = deepcopy(base)
        r = integrate_evidence(farm, p, s, f, base)
        self.assertEqual(base, before)
        self.assertEqual([x["crops"] for x in r["scenarios"]], [x["crops"] for x in base["scenarios"]])
        self.assertEqual(len(r["scenarios"]), 3)
        self.assertEqual(len(r["gaezEvidence"]["results"]), 28)
        self.assertEqual(r["gaezEvidence"]["context"]["farmerInputs"]["previousCrops"], ["Soybean", "Rice"])
        self.assertIn("Limited or unknown irrigation", " ".join(r["gaezEvidence"]["planningNotes"]))
        self.assertIn("Generic Rice", " ".join(r["gaezEvidence"]["warnings"]))
        self.assertTrue(any(x["id"] == "FAO_GAEZ_V5_SIX" for x in r["references"]))
        self.assertFalse(model_status()["predictionsEnabled"])

    def test_no_source_still_preserves_reference_planner(self):
        farm, p, s, f, base = self.fixture()
        with patch("backend.gaez.service.read_manifest", side_effect=SourceUnavailable("synthetic outage")):
            r = integrate_evidence(farm, p, s, f, base)
        self.assertEqual(r["gaezEvidence"]["status"], "unavailable")
        self.assertEqual(r["gaezEvidence"]["results"], [])
        self.assertEqual([x["crops"] for x in r["scenarios"]], [x["crops"] for x in base["scenarios"]])

    def test_soil_sources_and_periods_stay_separate(self):
        farm, p, s, f, base = self.fixture()
        f["soilInputs"] = {"ph": {"value": 7.1, "source": "PROXY_DEMO_ONLY", "depthCm": "0-5"}}
        r = integrate_evidence(farm, p, s, f, base)["gaezEvidence"]
        self.assertEqual(r["context"]["soilEvidence"], f["soilInputs"])
        self.assertEqual(r["context"]["nasaReferencePeriod"], s["referencePeriod"])
        self.assertEqual(r["dataset"]["referencePeriod"], "2001-2020")
        self.assertFalse(r["context"]["mlPredictionsEnabled"])

    def test_full_soil_provenance_is_copied_without_verification_upgrade(self):
        farm, p, s, f, base = self.fixture()
        source = {"farmerMeasurements": [{"measuredOn": "2026-01-01", "depthTopCm": 0,
                  "depthBottomCm": 5, "source": "laboratory_confirmed",
                  "verification": "Farmer-reported laboratory result; not independently verified"}]}
        r = integrate_evidence(farm, p, s, f, base, soil_provenance=source)
        self.assertEqual(r["gaezEvidence"]["context"]["soilProvenance"], source)
        source["farmerMeasurements"].clear()
        self.assertEqual(len(r["gaezEvidence"]["context"]["soilProvenance"]["farmerMeasurements"]), 1)


class GaezOwnershipApiTests(unittest.TestCase):
    def setUp(self):
        self.connection = engine.connect()
        self.transaction = self.connection.begin()
        self.db = Session(bind=self.connection, join_transaction_mode="create_savepoint")
        app.dependency_overrides[get_db] = lambda: self.db
        self.client = TestClient(app)
        self.other = TestClient(app)
        r = self.client.post("/api/farms", json={"name": "Synthetic GAEZ API test",
            "latitude": 34.5004, "longitude": -91.5526, "locationName": "Synthetic Stuttgart",
            "currentCrop": "Rice", "irrigation": "limited", "goal": "conserve_water"})
        self.assertEqual(r.status_code, 201)
        self.id = r.json()["id"]

    def tearDown(self):
        self.client.close()
        self.other.close()
        app.dependency_overrides.clear()
        self.db.close()
        self.transaction.rollback()
        self.connection.close()

    def test_owner_can_read_published_assessment_other_owner_cannot(self):
        url = f"/api/farms/{self.id}/gaez"
        data = {"cropCode": "SOY", "scenario": "LRLM"}
        self.assertEqual(self.other.post(url, json=data).status_code, 404)
        r = self.client.post(url, json=data)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "available")
        self.assertEqual(r.json()["sampling"]["latitude"], 34.5004)

    def test_unsupported_crop_no_fake_class(self):
        r = self.client.post(f"/api/farms/{self.id}/gaez",
                             json={"cropCode": "FAKE", "scenario": "LRLM"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "unsupported")
        self.assertIsNone(r.json()["rawValue"])

    def test_limited_water_caution_covers_both_irrigated_scenarios(self):
        for scenario in ["LILM", "HILM"]:
            r = self.client.post(f"/api/farms/{self.id}/gaez",
                                 json={"cropCode": "RCW", "scenario": scenario})
            self.assertEqual(r.status_code, 200)
            self.assertIn("Farmer-reported irrigation: limited", " ".join(r.json()["warnings"]))
            self.assertIn("does not establish", " ".join(r.json()["warnings"]))

    def test_arbitrary_urls_and_coordinate_override_are_rejected(self):
        r = self.client.post(f"/api/farms/{self.id}/gaez", json={
            "cropCode": "WHE", "scenario": "LRLM", "url": "http://localhost", "latitude": 0})
        self.assertEqual(r.status_code, 422)
