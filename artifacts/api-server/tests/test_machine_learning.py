"""Offline software tests. Synthetic values/models below are TEST ONLY.

They never constitute scientific training or evaluation evidence.
"""
import copy
import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

import httpx
import joblib
import numpy as np
import pandas as pd
import rasterio
from rasterio.transform import from_origin
from sklearn.dummy import DummyRegressor
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold

from backend.machine_learning import contract as c
from backend.machine_learning.common import digest, read_json, write_json, sha256
from backend.machine_learning.dataset import validate_dataset, quality_report
from backend.machine_learning.download import download
from backend.machine_learning.environment import power_features, soil_mean, native_soil_mean
from backend.machine_learning.inference import SuitabilityPredictor
from backend.machine_learning.labels import cell_at, raster_metadata, verify_metadata, catalog_selection
from backend.machine_learning.evidence import finalize
from backend.machine_learning.supplement import supplement
from backend.machine_learning.spatial import split, assert_no_leakage, buffered_cv
from backend.machine_learning.training import (
    acceptance, breakdown, metrics, pipeline, train, versions, DEFAULT_CONFIG,
)

FIXTURES = Path(__file__).parent / "fixtures/phase4"


def features(crop="WHE", temperature=20.0):
    return {
        **{f"tmean_m{m:02}": temperature for m in range(1, 13)},
        **{f"rain_m{m:02}": 100.0 for m in range(1, 13)},
        "clay_pct": 30.0, "sand_pct": 40.0, "silt_pct": 30.0,
        "ph": 7.0, "soc_g_kg": 15.0, "crop": crop, "scenario": "LRLM",
    }


def synthetic_frame():
    rows = []
    for i, lat in enumerate(range(-45, 66, 10)):
        for j, lon in enumerate(range(-165, 166, 20)):
            for k, crop in enumerate(c.CROPS):
                temperature = 5+(i*17+j)%30
                rows.append({**features(crop, float(temperature)), "cell_id": f"TEST:{i}:{j}",
                             "latitude": float(lat), "longitude": float(lon),
                             "target": temperature*100 + k*300, "period": c.PERIOD})
    return pd.DataFrame(rows)


def synthetic_power():
    # Complete calendar solely to test aggregation and period validation.
    vals = {}
    day = date(2001, 1, 1)
    while day <= date(2020, 12, 31):
        vals[day.strftime("%Y%m%d")] = 1.0
        day += timedelta(days=1)
    return {"header": {"time_standard": "UTC", "fill_value": -999},
            "parameters": {"T2M": {"units": "C"}, "PRECTOTCORR": {"units": "mm/day"}},
            "properties": {"parameter": {"T2M": vals.copy(), "PRECTOTCORR": vals.copy()}}}


class ContractTests(unittest.TestCase):
    def test_valid_features(self):
        c.validate_features(features())

    def test_input_screening(self):
        for key, val in [("ph", 15), ("clay_pct", -1), ("rain_m01", -2),
                         ("tmean_m01", float("nan")), ("soc_g_kg", True),
                         ("crop", "rice"), ("scenario", "HILM")]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                c.validate_features({**features(), key: val})

    def test_no_extra_target_or_coordinate_feature(self):
        for key in ("target", "latitude", "longitude"):
            with self.assertRaisesRegex(ValueError, "schema"):
                c.validate_features({**features(), key: 10})

    def test_bad_texture(self):
        with self.assertRaisesRegex(ValueError, "texture"):
            c.validate_features({**features(), "sand_pct": 10})

    def test_coordinates(self):
        for lat, lon in [(91, 0), (0, 181), (float("nan"), 0), (True, 0), ("20", 10)]:
            with self.assertRaises(ValueError):
                c.coordinates(lat, lon)

    def test_missing_model_is_explicit(self):
        r = SuitabilityPredictor().predict(c.PredictionInput(20, 30, features()))
        self.assertEqual(r["reasons"], ["missing_accepted_model"])
        self.assertNotIn("prediction", r)
        self.assertNotIn("confidence", r)


class AcquisitionTests(unittest.TestCase):
    def test_authentic_source_fixture(self):
        fixture = read_json(FIXTURES / "gaez_cells.json")
        self.assertEqual(fixture["license"], "CC-BY-4.0")
        self.assertEqual({r["crop"] for r in fixture["records"]}, set(c.CROPS))
        for r in fixture["records"]:
            self.assertGreaterEqual(r["target"], 0)
            self.assertLessEqual(r["target"], 10000)
            self.assertEqual(len(r["label_sha256"]), 64)
        path = FIXTURES / "gaez_brl_window.tif"
        self.assertEqual(sha256(path), fixture["window"]["sha256"])
        with rasterio.open(path) as src:
            row = fixture["records"][0]
            rr, cc = cell_at(src, row["latitude"], row["longitude"])
            self.assertEqual((rr, cc), (1, 1))
            self.assertEqual(int(src.read(1)[rr, cc]), row["target"])
            self.assertEqual(src.nodata, -9)

    def test_missing_and_corrupt_files(self):
        with self.assertRaises(FileNotFoundError):
            read_json(FIXTURES / "not_present.json")
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "bad.json"
            path.write_text("bad")
            with self.assertRaises(json.JSONDecodeError):
                read_json(path)
            with self.assertRaises(rasterio.errors.RasterioIOError):
                raster_metadata(path)

    def test_small_fixture_cannot_impersonate_global_raster(self):
        with self.assertRaises(ValueError):
            raster_metadata(FIXTURES / "gaez_brl_window.tif")

    def test_outside_source(self):
        with rasterio.open(FIXTURES / "gaez_brl_window.tif") as src:
            with self.assertRaisesRegex(ValueError, "outside"):
                cell_at(src, -80, -170)

    def test_projected_crs_uses_xy_order(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "projected.tif"
            with rasterio.open(path, "w", driver="GTiff", width=10, height=10, count=1,
                               dtype="int16", crs="EPSG:3857",
                               transform=from_origin(0, 10000, 1000, 1000), nodata=-9) as dst:
                dst.write(np.zeros((1, 10, 10), dtype="int16"))
            with rasterio.open(path) as src:
                self.assertEqual(cell_at(src, .045, .005), (4, 0))

    def test_official_metadata_fixture(self):
        audit = read_json(Path("docs/phase4/evidence/source-audit.json"))
        self.assertEqual(audit["sampled_cells"], 180)
        self.assertTrue(all(x["archive_bytes_match"] for x in audit["historical_files"]))

    def test_unverified_metadata_rejected(self):
        with self.assertRaises((KeyError, ValueError)):
            verify_metadata({"result": {}})

    def test_bad_catalog_fails(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "bad.xlsx"
            path.write_bytes(b"not excel")
            with self.assertRaises(ValueError):
                catalog_selection(path)

    def test_cached_download_hash_and_url_enforced(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "a.json"
            path.write_text("{}")
            url = "https://power.larc.nasa.gov/example"
            write_json(path.with_suffix(".json.source.json"),
                       {"url": url, "sha256": sha256(path)})
            with patch("httpx.Client", side_effect=AssertionError("must use cache")):
                self.assertEqual(download(url, path)["sha256"], sha256(path))
            path.write_text("corrupt")
            with self.assertRaisesRegex(ValueError, "hash"):
                download(url, path)

    def test_nonofficial_download_rejected(self):
        with tempfile.TemporaryDirectory() as root, self.assertRaises(ValueError):
            download("http://example.org/labels.tif", Path(root)/"x")

    def test_resumable_download(self):
        original_client = httpx.Client
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)/"data.bin"
            url = "https://files.isric.org/test.bin"
            path.with_suffix(".bin.part").write_bytes(b"abc")
            write_json(path.with_suffix(".bin.part.json"), {"url": url, "etag": '"v1"'})

            def handler(request):
                self.assertEqual(request.headers["range"], "bytes=3-")
                self.assertEqual(request.headers["if-range"], '"v1"')
                return httpx.Response(206, content=b"def", headers={
                    "content-range": "bytes 3-5/6", "etag": '"v1"'})

            transport = httpx.MockTransport(handler)
            with patch("backend.machine_learning.download.httpx.Client",
                       side_effect=lambda **kwargs: original_client(transport=transport)), \
                    patch("backend.machine_learning.download.time.sleep"):
                evidence = download(url, path)
            self.assertEqual(path.read_bytes(), b"abcdef")
            self.assertEqual(evidence["sha256"], sha256(path))

    def test_bounded_retry_and_size_budget(self):
        original_client = httpx.Client
        for mode in ("retry", "budget"):
            calls = []

            def handler(request):
                calls.append(request)
                if mode == "retry":
                    return httpx.Response(503)
                return httpx.Response(200, content=b"too much data")

            with tempfile.TemporaryDirectory() as root, \
                    patch("backend.machine_learning.download.httpx.Client",
                          side_effect=lambda **kwargs: original_client(transport=httpx.MockTransport(handler))), \
                    patch("backend.machine_learning.download.time.sleep"):
                with self.assertRaises((httpx.HTTPStatusError, ValueError)):
                    download("https://files.isric.org/test.bin", Path(root)/"x",
                             max_bytes=2, attempts=2)
                self.assertEqual(len(calls), 2 if mode == "retry" else 1)

    def test_native_tile_subsetting_and_mask_replay(self):
        from pyproj import CRS
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            vrt = root/"clay_0-5cm_mean.vrt"
            crs = CRS.from_epsg(6933)
            source_url = "https://files.isric.org/test/clay.vrt"
            tile_url = "https://files.isric.org/test/tile.tif"
            tile = root / ("tile-" + digest(tile_url)[:24] + ".tif")
            with rasterio.open(tile, "w", driver="GTiff", width=80, height=80,
                               count=1, crs=crs, dtype="int16", nodata=-32768,
                               transform=from_origin(-10000, 10000, 250, 250)) as dst:
                dst.write(np.full((1, 80, 80), 300, dtype="int16"))
            vrt.write_text(f"""<VRTDataset><SRS>{crs.to_wkt()}</SRS>
<GeoTransform>-10000,250,0,10000,0,-250</GeoTransform><VRTRasterBand>
<NoDataValue>-32768</NoDataValue><ComplexSource><SourceFilename>tile.tif</SourceFilename>
<DstRect xOff="0" yOff="0" xSize="80" ySize="80"/></ComplexSource>
</VRTRasterBand></VRTDataset>""")
            write_json(vrt.with_suffix(".vrt.source.json"), {"url": source_url})
            with patch("backend.machine_learning.environment.download",
                       return_value={"url": tile_url, "sha256": sha256(tile)}):
                value, evidence = native_soil_mean(vrt, 0, 0, root)
                self.assertEqual(value, 30)
                self.assertEqual(evidence["valid_area_fraction"], 1)
                self.assertEqual(evidence["nodata"], -32768)
                with rasterio.open(tile, "r+") as dst:
                    dst.write(np.full((1, 80, 80), -32768, dtype="int16"))
                with self.assertRaisesRegex(ValueError, "valid_area"):
                    native_soil_mean(vrt, 0, 0, root)

    def test_utc_complete_aggregation(self):
        result = power_features(synthetic_power())
        self.assertEqual(result["tmean_m01"], 1)
        self.assertEqual(result["rain_m01"], 31)
        self.assertEqual(result["rain_m02"], 28.25)

    def test_power_missing_period_fill_and_units(self):
        original = synthetic_power()
        for kind in ("period", "units", "missing", "nan", "fill", "time"):
            data = copy.deepcopy(original)
            if kind == "period":
                data["properties"]["parameter"]["T2M"].pop("20010101")
            elif kind == "units":
                data["parameters"]["T2M"]["units"] = "F"
            elif kind == "time":
                data["header"]["time_standard"] = "LST"
            else:
                data["properties"]["parameter"]["T2M"]["20010101"] = {
                    "missing": None, "nan": float("nan"), "fill": -999}[kind]
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                power_features(data)
        with self.assertRaisesRegex(ValueError, "period"):
            power_features(original, [2019, 2025])

    def test_soil_units_and_nodata(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)/"soil.tif"
            bounds = [10, 20, 10.01, 20.01]
            with rasterio.open(path, "w", driver="GTiff", count=1, width=4, height=4,
                               crs="EPSG:4326", dtype="int16", nodata=-32768,
                               transform=from_origin(10, 20.01, .0025, .0025)) as dst:
                dst.write(np.full((1, 4, 4), 300, dtype="int16"))
            self.assertEqual(soil_mean(path, bounds)[0], 30)
            with rasterio.open(path, "r+") as dst:
                dst.write(np.full((1, 4, 4), -32768, dtype="int16"))
            with self.assertRaisesRegex(ValueError, "valid_area"):
                soil_mean(path, bounds)

    def test_missing_mask_not_guessed_as_zero(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)/"soil.tif"
            with rasterio.open(path, "w", driver="GTiff", count=1, width=4, height=4,
                               crs="EPSG:4326", dtype="int16",
                               transform=from_origin(10, 20.01, .0025, .0025)) as dst:
                dst.write(np.zeros((1, 4, 4), dtype="int16"))
            with self.assertRaisesRegex(ValueError, "mask"):
                soil_mean(path, [10, 20, 10.01, 20.01])


class DatasetAndTrainingTests(unittest.TestCase):
    def test_duplicate_and_hash_validation(self):
        row = synthetic_frame().iloc[0].to_dict()
        bundle = {"contract": c.CONTRACT, "target": c.TARGET,
                  "source_manifest": {}, "records": [row, row], "exclusions": []}
        bundle["dataset_hash"] = digest(bundle)
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            validate_dataset(bundle, replay=False)
        bundle["records"] = []
        with self.assertRaisesRegex(ValueError, "hash"):
            validate_dataset(bundle, replay=False)

    def test_quality_reports_rejections(self):
        bundle = {"records": [], "exclusions": [{"excluded_rows": 5, "reason": "missing_soil"}],
                  "dataset_hash": "TEST_ONLY", "source_manifest": {"rasters": []}}
        report = quality_report(bundle)
        self.assertEqual(report["excluded_rows"], 5)
        self.assertEqual(report["final_examples"], 0)

    def test_saved_evidence_never_retrains_or_consumes_holdout(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            config = {**read_json(DEFAULT_CONFIG), "version": "TEST_ONLY_saved_config"}
            evidence = {"dataset_hash": "TEST_ONLY", "status": "insufficient_evidence",
                        "reasons": ["no_aligned_examples"], "supported_crops": [],
                        "model_saved": False, "contract": c.CONTRACT, "config": config}
            write_json(root/"prepared/quality.json", {
                "effective_label_cells": 0, "final_examples": 0, "excluded_rows": 5})
            write_json(root/"prepared/dataset.json", {
                "dataset_hash": "TEST_ONLY", "records": [], "sampling": {"requested_cells": 1},
                "source_manifest": {"rasters": [{"crop": "WHE"}]}})
            write_json(root/"training/readiness.json", evidence)
            with patch("backend.machine_learning.evidence.train", side_effect=AssertionError("do not retrain")):
                result = finalize(root, root/"evidence")
            self.assertFalse(result["phase4_complete"])
            self.assertFalse(result["final_holdout_evaluated"])
            self.assertEqual(read_json(root/"evidence/training-config.json"), config)

    def test_reproducible_leakage_free_splits(self):
        f = synthetic_frame()
        a, b = split(f), split(f.sample(frac=1, random_state=7))
        self.assertEqual(a.groupby("cell_id").split.first().to_dict(),
                         b.groupby("cell_id").split.first().to_dict())
        self.assertTrue(assert_no_leakage(a))
        self.assertEqual(a.groupby("cell_id").split.nunique().max(), 1)

    def test_supplement_is_geographic_not_target_selected(self):
        frame = synthetic_frame()
        candidate_rows = frame.to_dict("records")
        candidate_rows += [{**r, "cell_id": r["cell_id"]+":north",
                            "latitude": r["latitude"]+2} for r in frame.to_dict("records")]
        original_rows = candidate_rows[:5]
        manifest = {"rasters": [{"path": "/unused/TEST_ONLY/raster.tif"}]}
        original = {"source_manifest": manifest, "source_manifest_hash": digest(manifest),
                    "records": original_rows, "sampling": "TEST_ONLY", "seed": 42,
                    "requested_cells": 1}
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)/"TEST_ONLY_samples.json"
            write_json(path, original)
            with patch("backend.machine_learning.supplement.import_labels", return_value=manifest), \
                    patch("backend.machine_learning.supplement.validate_samples", return_value=True), \
                    patch("backend.machine_learning.supplement.sample_labels",
                          return_value={"records": candidate_rows}):
                result = supplement(path, Path(root)/"out.json")
                one = read_json(Path(root)/"out.json")
                # Change every candidate target; geography must remain identical.
                altered = [{**r, "target": 10000-r["target"]} for r in candidate_rows]
                with patch("backend.machine_learning.supplement.sample_labels",
                           return_value={"records": altered}):
                    supplement(path, Path(root)/"other.json")
                two = read_json(Path(root)/"other.json")
            self.assertEqual(result["additional_cells"], 120)
            self.assertEqual(result["quotas"], {"test": 60, "train": 40, "validation": 20})
            self.assertEqual([r["cell_id"] for r in one["records"]],
                             [r["cell_id"] for r in two["records"]])

    def test_nearby_points_get_buffered(self):
        f = synthetic_frame().iloc[:10].copy()
        f.loc[f.index[5:], "latitude"] = f.iloc[0].latitude+.1
        f.loc[f.index[5:], "longitude"] = f.iloc[0].longitude+.1
        # Force a block boundary assignment conflict; buffering must remove it.
        with patch("backend.machine_learning.spatial.partition", side_effect=["test", "train", "test", "train", "test", "train"]):
            result = split(f)
        self.assertIn("buffer_excluded", set(result.split))
        self.assertTrue(assert_no_leakage(result))

    def test_buffered_training_cv(self):
        frame = split(synthetic_frame())
        frame = frame[frame.split == "train"].reset_index(drop=True)
        raw = GroupKFold(3).split(frame, groups=frame.block)
        for tr, va in buffered_cv(frame, raw):
            self.assertFalse(set(frame.iloc[tr].cell_id) & set(frame.iloc[va].cell_id))

    def test_baseline_metrics_and_serialization(self):
        f = synthetic_frame().iloc[:100]
        model = pipeline(DummyRegressor()).fit(f[c.FEATURES], f.target)
        result = breakdown(f.assign(region="TEST_ONLY"), model.predict(f[c.FEATURES]))
        self.assertEqual(result["aggregate"]["count"], 100)
        self.assertEqual(metrics([0, 2], [1, 1])["mae"], 1)
        self.assertIsNone(metrics([0, 0], [0, 0])["r2"])
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)/"TEST_ONLY.joblib"
            joblib.dump(model, path)
            np.testing.assert_equal(model.predict(f[c.FEATURES]),
                                    joblib.load(path).predict(f[c.FEATURES]))

    def test_preprocessing_never_fitted_on_holdout(self):
        f = synthetic_frame().iloc[:100]
        model = pipeline(Ridge()).fit(f[c.FEATURES], f.target)
        means = model.named_steps["features"].named_transformers_["numeric"].mean_.copy()
        changed = f.copy()
        changed["tmean_m01"] = 10000
        model.predict(changed[c.FEATURES])
        np.testing.assert_equal(means, model.named_steps["features"].named_transformers_["numeric"].mean_)

    def test_acceptance_rejects_bad_model(self):
        bad = {"aggregate": {"mae": 5000, "r2": -1}, "per_crop": {}, "per_region": {}}
        baseline = {"aggregate": {"mae": 2000}}
        self.assertIn("aggregate_mae", acceptance(
            {"candidate": bad, "dummy": baseline, "crop_mean": baseline},
            read_json(DEFAULT_CONFIG)))

    def test_readiness_stops_before_training_or_holdout(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)/"dataset.json"
            write_json(path, {"dataset_hash": "TEST_ONLY", "source_manifest": {},
                              "records": [], "samples_sha256": "TEST_ONLY", "sampling": {}})
            with patch("backend.machine_learning.training.validate_dataset", return_value=pd.DataFrame()):
                result = train(path, Path(root)/"out")
            self.assertEqual(result["status"], "insufficient_evidence")
            self.assertFalse((Path(root)/"out/accepted.joblib").exists())
            self.assertFalse((Path(root)/".holdout").exists())

    def test_training_to_accepted_serialization_and_once_only_holdout(self):
        # Exercises plumbing ONLY, bypassing genuine-source ingestion explicitly.
        # Uses temporary test-only artifacts and never reports these as real metrics.
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            config = read_json(DEFAULT_CONFIG)
            config.update(forest_trees=3, ridge_alpha=[1.0],
                          forest_min_samples_leaf=[3],
                          minimum_label_span=2000,
                          minimum_test_cells_per_region=1)
            config_path = root/"TEST_ONLY_config.json"
            write_json(config_path, config)
            path = root/"TEST_ONLY_dataset.json"
            write_json(path, {"dataset_hash": "SYNTHETIC_TEST_ONLY", "source_manifest": {},
                              "records": [], "samples_sha256": "TEST_ONLY", "sampling": {}})
            with patch("backend.machine_learning.training.validate_dataset",
                       return_value=synthetic_frame()):
                result = train(path, root/"out", config_path)
                self.assertEqual(result["status"], "accepted")
                loaded = SuitabilityPredictor(root/"out")
                self.assertIsNotNone(loaded.model)
                with self.assertRaises(FileExistsError):
                    train(path, root/"other-output", config_path)
            # Tampering with bytes must fail before unpickling.
            artifact = root/"out/accepted.joblib"
            artifact.write_bytes(b"corrupt")
            self.assertEqual(SuitabilityPredictor(root/"out").reason, "corrupt_model_artifact")


class InferenceTests(unittest.TestCase):
    def setUp(self):
        # Test-only model fitted in memory, never production evidence or persisted.
        f = synthetic_frame().iloc[:100]
        self.predictor = SuitabilityPredictor()
        self.predictor.model = pipeline(DummyRegressor()).fit(f[c.FEATURES], f.target)
        self.predictor.reason = None
        self.predictor.metadata = {
            "model_version": "SYNTHETIC_SOFTWARE_TEST_ONLY", "supported_crops": list(c.CROPS),
            "supported_scenarios": ["LRLM"], "support": {
                "ranges": {k: [-100000, 100000] for k in c.NUMERIC},
                "heldout_blocks": ["11:21"],
                "scaler_mean": [0]*len(c.NUMERIC), "scaler_scale": [1]*len(c.NUMERIC),
                "training_environments": [{k: features()[k] for k in c.NUMERIC}],
                "distance_threshold": 1.0,
            }}
        self.request = c.PredictionInput(20, 30, features())

    def test_success_has_target_not_confidence(self):
        result = self.predictor.predict(self.request)
        self.assertTrue(result["available"])
        self.assertIn("prediction", result)
        self.assertNotIn("confidence", result)
        self.assertIn("not", result["target"])

    def test_failure_paths_never_contain_scores(self):
        from dataclasses import replace
        for change in [
            {"features": {**features(), "crop": "rice"}},
            {"features": {**features(), "scenario": "HILM"}},
            {"features": {k: v for k, v in features().items() if k != "ph"}},
            {"features": {**features(), "ph": None}},
            {"features": {**features(), "ph": float("nan")}},
            {"features": {**features(), "target": 1000}},
            {"schema_version": "old"}, {"units": {}}, {"period": [2019, 2025]},
            {"latitude": 99}, {"longitude": 100}, {"climate_source": "unavailable"},
            {"soil_source": "PROXY_DEMO_ONLY"}, {"source_quality": "farmer_reported"},
            {"soil_depth_cm": [5, 15]}, {"soil_statistic": "median"},
            {"spatial_rule": "nearest_town"},
            {"features": {**features(), "tmean_m01": 69}},
        ]:
            with self.subTest(change=change):
                result = self.predictor.predict(replace(self.request, **change))
                self.assertFalse(result["available"])
                self.assertNotIn("prediction", result)

    def test_failed_estimator_is_unavailable(self):
        with patch.object(self.predictor.model, "predict", side_effect=RuntimeError("failed")):
            self.assertEqual(self.predictor.predict(self.request)["status"], "unavailable")

    def test_missing_or_corrupt_bundle(self):
        with tempfile.TemporaryDirectory() as root:
            self.assertIsNone(SuitabilityPredictor(root).model)
            (Path(root)/"accepted.joblib").write_bytes(b"not pickle")
            write_json(Path(root)/"evaluation.json", {"status": "rejected"})
            p = SuitabilityPredictor(root)
            self.assertIsNone(p.model)
            self.assertNotIn("prediction", p.predict(self.request))

    def test_model_version_rejected_before_unpickle(self):
        with tempfile.TemporaryDirectory() as root:
            (Path(root)/"accepted.joblib").write_bytes(b"never unpickle this")
            write_json(Path(root)/"evaluation.json", {
                "status": "accepted", "model_saved": True, "test": {}, "config": {},
                "contract": {"version": "obsolete"},
            })
            with patch("backend.machine_learning.inference.acceptance", return_value=[]), \
                    patch("joblib.load", side_effect=AssertionError("unsafe load")):
                result = SuitabilityPredictor(root)
                self.assertIsNone(result.model)
                self.assertEqual(result.reason, "incompatible_model_or_preprocessing")


if __name__ == "__main__":
    unittest.main()
