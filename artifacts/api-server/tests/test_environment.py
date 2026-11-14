"""Run: PYTHONPATH=artifacts/api-server uv run python -m unittest discover -s artifacts/api-server/tests -v"""
import calendar
import copy
import csv
import io
import math
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, MagicMock
from zipfile import ZipFile
import httpx
from pydantic import ValidationError
from backend.environment.validation import parse_date, numeric, coords, soil_values
from backend.environment.calculations import aggregate, longest_dry_spell, summarize, daily_rows
from backend.environment.constants import PARAMETERS, WETNESS, CLIMATE, LOCATIONS, location_key
from backend.environment.importer import read_csv, extract_bundle, FILES
from backend.environment.power_client import parse_response, request_group
from backend.schemas import MeasurementInput


def day(d, **values):
    return {"date": str(d), **{p: None for p in PARAMETERS}, **values}


def month(year, month, **values):
    return [day(date(year, month, i), **values) for i in range(1, calendar.monthrange(year, month)[1]+1)]


class ValidationTests(unittest.TestCase):
    def test_valid_date(self):
        self.assertEqual(parse_date("2020-02-29"), date(2020, 2, 29))

    def test_bad_dates(self):
        for value in ("2019-02-29", "2026-01-01", "01/01/2019"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_date(value)

    def test_missing_markers(self):
        for value in ("", "-999", "-9999", None):
            self.assertIsNone(numeric(value, "T2M")[0])

    def test_zero_is_not_missing(self):
        self.assertEqual(numeric("0", "PRECTOTCORR"), (0, "valid"))

    def test_numeric_screening(self):
        for value, p in [("inf", "T2M"), ("-0.1", "PRECTOTCORR"), ("101", "RH2M"), ("1.01", "GWETROOT"), ("text", "T2M")]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                numeric(value, p)

    def test_custom_fill(self):
        self.assertIsNone(numeric("-888", "T2M", -888)[0])

    def test_coordinates(self):
        self.assertEqual(coords(90, -180), (90, -180))
        for lat, lon in [(91, 0), (0, 181), (float("nan"), 0)]:
            with self.assertRaises(ValueError):
                coords(lat, lon)

    def test_exact_point_not_nearest_city(self):
        self.assertNotEqual(location_key(32.56, 35.84), location_key(32.55696, 35.8479))

    def test_csv_headers(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/"a.csv"
            p.write_text("location_id,date,T2M\nirbid,2020-01-01,12\n")
            headers, rows = read_csv(p, {"location_id", "date"})
            self.assertEqual(rows[0]["T2M"], "12")

    def test_missing_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/"a.csv"
            p.write_text("location_id,T2M\nirbid,12\n")
            with self.assertRaises(ValueError):
                read_csv(p, {"date"})

    def test_malformed_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/"a.csv"
            p.write_text("a,b\n1,2,3\n")
            with self.assertRaises(ValueError):
                read_csv(p, {"a"})

    def test_zip_whitelist_and_unchanged_extraction(self):
        with tempfile.TemporaryDirectory() as tmp:
            p, out = Path(tmp)/"data.zip", Path(tmp)/"imports"
            with ZipFile(p, "w") as z:
                for f in FILES:
                    z.writestr(f, b"a,b\r\n1,2\r\n")
                z.writestr("../escape", "should not be extracted")
            with patch("backend.environment.importer.IMPORT_DIR", out):
                hashes = extract_bundle(p)
                self.assertEqual(len(hashes), 4)
                self.assertEqual((out/"nasa_daily.csv").read_bytes(), b"a,b\r\n1,2\r\n")
                self.assertFalse((Path(tmp)/"escape").exists())
                (out/"nasa_daily.csv").write_bytes(b"changed")
                with self.assertRaises(ValueError):
                    extract_bundle(p)


class CalculationTests(unittest.TestCase):
    def test_monthly_temperature_means(self):
        rows = month(2025, 1, T2M=10, T2M_MAX=20, T2M_MIN=5)
        rows[0]["T2M"] = 41
        result = aggregate(rows, 31)
        self.assertEqual(result["T2M"], 11)
        self.assertEqual(result["T2M_MAX"], 20)
        self.assertEqual(result["T2M_MIN"], 5)

    def test_monthly_rainfall_sum(self):
        self.assertEqual(aggregate(month(2020, 2, PRECTOTCORR=2), 29)["PRECTOTCORR"], 58)

    def test_missing_day_invalidates_total(self):
        rows = month(2025, 1, PRECTOTCORR=1, T2M=10)
        rows[2]["PRECTOTCORR"] = None
        r = aggregate(rows, 31)
        self.assertIsNone(r["PRECTOTCORR"])
        self.assertEqual(r["T2M"], 10)
        self.assertEqual(r["validDays"]["PRECTOTCORR"], 30)

    def test_absent_day_not_zero_filled(self):
        self.assertIsNone(aggregate(month(2025, 1, T2M=10)[:-1], 31)["T2M"])

    def test_hot_days_strict_threshold(self):
        rows = [day("2025-01-01", T2M_MAX=35), day("2025-01-02", T2M_MAX=35.01)]
        r = aggregate(rows, 2)
        self.assertEqual(r["hotDays35"], 1)
        self.assertEqual(r["hotDays30"], 2)

    def test_annual_total_and_weighted_mean(self):
        rows = []
        for m in range(1, 13):
            rows.extend(month(2024, m, T2M=m, PRECTOTCORR=2))
        r = summarize(rows)["annual"][5]
        self.assertEqual(r["PRECTOTCORR"], 732)
        self.assertAlmostEqual(r["T2M"], sum(i["T2M"] for i in rows)/366)

    def test_anomalies_complete_month_only(self):
        rows = month(2019, 1, PRECTOTCORR=1, GWETTOP=.2)+month(2020, 1, PRECTOTCORR=3, GWETTOP=.6)
        results = summarize(rows)["monthly"]
        self.assertEqual(results[0]["PRECTOTCORRAnomaly"], -31)
        self.assertAlmostEqual(results[0]["GWETTOPAnomaly"], -.2)
        self.assertEqual(results[0]["PRECTOTCORRReferenceYears"], 2)
        self.assertIsNone(results[24]["PRECTOTCORRAnomaly"])

    def test_dry_runs_reset_on_missing_and_gaps(self):
        rows = [day("2025-01-01", PRECTOTCORR=0), day("2025-01-02", PRECTOTCORR=0),
                day("2025-01-03"), day("2025-01-05", PRECTOTCORR=0), day("2025-01-06", PRECTOTCORR=2)]
        self.assertEqual(longest_dry_spell(rows, 1), 2)
        self.assertEqual(longest_dry_spell(rows, 0), 0)

    def test_empty_series(self):
        r = summarize([])
        self.assertEqual(len(r["monthly"]), 84)
        self.assertTrue(all(m["T2M"] is None for m in r["monthly"]))
        self.assertIsNone(r["annual"][0]["longestDrySpell"])

    def test_daily_rows_preserve_null(self):
        r = daily_rows([SimpleNamespace(date=date(2025, 1, 1), parameter="T2M", value=0)])
        self.assertEqual(r[0]["T2M"], 0)
        self.assertIsNone(r[0]["GWETROOT"])


class SoilAndFarmerTests(unittest.TestCase):
    def setUp(self):
        self.row = {"clay_pct": "40", "sand_pct": "20", "silt_pct": "40", "ph": "7.1", "soc_g_kg": "12"}
        self.measurement = {"parameter": "soil_moisture", "value": .3, "unit": "m3/m3",
            "depthTopCm": 0, "depthBottomCm": 5, "measuredOn": "2025-01-01", "source": "farmer_reported"}

    def test_soil_texture(self):
        self.assertEqual(soil_values(self.row)["ph"]["value"], 7.1)

    def test_texture_total(self):
        self.row["sand_pct"] = "50"
        with self.assertRaises(ValueError):
            soil_values(self.row)

    def test_missing_soil_value(self):
        self.row["clay_pct"] = ""
        self.assertIsNone(soil_values(self.row)["clay_pct"]["value"])

    def test_ph_and_carbon_ranges(self):
        for key, value in [("ph", "15"), ("soc_g_kg", "-1")]:
            row = {**self.row, key: value}
            with self.assertRaises(ValueError):
                soil_values(row)

    def test_units_and_depth(self):
        m = MeasurementInput(**self.measurement)
        self.assertEqual(m.value, .3)
        for changes in [{"value": 2}, {"unit": "g/kg"}, {"depthTopCm": None}, {"depthBottomCm": 0}, {"value": float("nan")}]:
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                MeasurementInput(**{**self.measurement, **changes})

    def test_laboratory_source_kept_separate(self):
        m = MeasurementInput(**{**self.measurement, "source": "laboratory_confirmed"})
        self.assertEqual(m.source, "laboratory_confirmed")


class NasaClientTests(unittest.TestCase):
    def payload(self):
        return {"header": {"time_standard": "UTC", "fill_value": -999},
            "parameters": {p: {"units": PARAMETERS[p][0]} for p in PARAMETERS},
            "properties": {"parameter": {p: {"20250101": .5 if p.startswith("GWET") else 1} for p in PARAMETERS}}}

    def parse(self, payload, params):
        return parse_response(payload, params, SimpleNamespace(key="32.55696,35.84790", latitude=32.55696, longitude=35.8479), "https://power.larc.nasa.gov/")

    def test_parameter_metadata_and_classification(self):
        records, warnings = self.parse(self.payload(), ["T2M", "GWETTOP"])
        self.assertEqual(records[0]["classification"], CLIMATE)
        self.assertEqual(records[1]["classification"], WETNESS)
        self.assertEqual(records[1]["unit"], "1")

    def test_missing_parameter_partial(self):
        p = self.payload()
        del p["properties"]["parameter"]["GWETTOP"]
        records, warnings = self.parse(p, ["T2M", "GWETTOP"])
        self.assertEqual(len(records), 1)
        self.assertTrue(warnings)

    def test_wrong_unit_rejected(self):
        p = self.payload()
        p["parameters"]["T2M"]["units"] = "F"
        with self.assertRaises(ValueError):
            self.parse(p, ["T2M"])

    def test_fill_value_remains_null(self):
        p = self.payload()
        p["properties"]["parameter"]["T2M"]["20250101"] = -999
        self.assertIsNone(self.parse(p, ["T2M"])[0][0]["value"])

    def test_invalid_live_values_rejected(self):
        p = self.payload()
        p["properties"]["parameter"]["GWETTOP"]["20250101"] = 2
        with self.assertRaises(ValueError):
            self.parse(p, ["GWETTOP"])

    def test_422_no_retry(self):
        client = MagicMock()
        client.get.return_value = httpx.Response(422, request=httpx.Request("GET", "https://power.larc.nasa.gov/"))
        with self.assertRaisesRegex(ValueError, "422"):
            request_group(client, 0, 0, ["T2M"])
        self.assertEqual(client.get.call_count, 1)

    @patch("backend.environment.power_client.time.sleep")
    def test_timeout_bounded_retries(self, sleep):
        client = MagicMock()
        client.get.side_effect = httpx.ReadTimeout("timeout")
        with self.assertRaises(httpx.ReadTimeout):
            request_group(client, 0, 0, ["T2M"])
        self.assertEqual(client.get.call_count, 2)

    @patch("backend.environment.power_client.time.sleep")
    def test_server_failure_bounded_retries(self, sleep):
        client = MagicMock()
        client.get.return_value = httpx.Response(503, request=httpx.Request("GET", "https://power.larc.nasa.gov/"))
        with self.assertRaises(httpx.HTTPStatusError):
            request_group(client, 0, 0, ["T2M"])
        self.assertEqual(client.get.call_count, 2)


if __name__ == "__main__":
    unittest.main()
