"""Fixed-bundle, idempotent ingestion with per-file validation and audit reports.

Use: uv run python -m backend.environment.importer --zip PATH
with PYTHONPATH=artifacts/api-server. Public callers cannot select paths.
"""
import argparse
import calendar
import csv
import hashlib
import io
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from zipfile import ZipFile
from sqlalchemy import select, text
from ..database import SessionLocal
from ..models import EnvironmentalValue, SoilEstimate, IngestionReport
from .constants import LOCATIONS, PARAMETERS, CLIMATE, WETNESS, POWER_URL, METADATA_URL
from .validation import parse_date, numeric, coords, soil_values
from .storage import ensure_location, store_values
from .calculations import daily_rows, summarize

ROOT = Path(__file__).resolve().parents[4]
IMPORT_DIR = ROOT / "data" / "imports"
DEFAULT_ZIP = ROOT / "attached_assets" / "Field_Shift_Replit_Data_1794680523930.zip"
FILES = {
    "nasa_daily.csv": {"location_id", "date"},
    "nasa_monthly.csv": {"location_id", "month", "temp_mean_c", "rain_total_mm", "humidity_mean_pct", "days_max_over_35c", "temp_valid_days", "rain_valid_days", "days_in_month"},
    "nasa_soil_moisture_daily.csv": {"location_id", "date", "data_classification", "units", "GWETTOP", "GWETROOT", "source_url"},
    "soilgrids_0_5cm_aligned.csv": {"location_id", "original_latitude", "original_longitude", "sample_latitude", "sample_longitude", "offset_km", "depth_cm", "source", "classification", "status", "sample_status", "clay_pct", "sand_pct", "silt_pct", "ph", "soc_g_kg", "texture_sum_pct", "texture_quality", "error"},
}


def read_csv(path, required):
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        if len(set(headers)) != len(headers) or not required.issubset(headers):
            raise ValueError(f"Missing or duplicate columns. Required: {', '.join(sorted(required))}")
        rows = list(reader)
        if any(None in row or any(v is None for v in row.values()) for row in rows):
            raise ValueError("Malformed CSV row lengths")
        return headers, rows


def extract_bundle(path):
    IMPORT_DIR.mkdir(parents=True, exist_ok=True)
    with ZipFile(path) as bundle:
        names = bundle.namelist()
        if not set(FILES).issubset(names):
            raise ValueError("ZIP is missing expected datasets")
        if sum(i.file_size for i in bundle.infolist()) > 30_000_000:
            raise ValueError("Bundle exceeds 30 MB safety limit")
        hashes = {}
        for name in FILES:
            raw = bundle.read(name)
            target = IMPORT_DIR / name
            if target.exists() and target.read_bytes() != raw:
                raise ValueError(f"{name} already exists with different bytes; refusing to overwrite original")
            target.write_bytes(raw)
            hashes[name] = hashlib.sha256(raw).hexdigest()
    return hashes


def source_url(lat, lon, params, utc=False):
    return f"{POWER_URL}?parameters={','.join(params)}&community=AG&latitude={lat}&longitude={lon}&start=20190101&end=20251231&format=JSON" + ("&time-standard=UTC" if utc else "")


def _import_bundle(path=DEFAULT_ZIP):
    started = datetime.now(timezone.utc)
    with SessionLocal() as db:
        # Transaction-scoped PostgreSQL lock prevents two operators importing together.
        db.execute(text("SELECT pg_advisory_xact_lock(746219002)"))
        audit = IngestionReport(source=Path(path).name, status="running", report={})
        db.add(audit)
        db.flush()
        report = {"files": [], "errors": [], "warnings": [], "startedAt": started.isoformat()}
        try:
            hashes = extract_bundle(path)
        except Exception as exc:
            report["errors"].append(str(exc))
            audit.status, audit.report, audit.completed_at = "failed", report, datetime.now(timezone.utc)
            db.commit()
            return {"id": audit.id, **report, "status": "failed"}
        locations = {id: ensure_location(db, lat, lon, id) for id, (_, lat, lon) in LOCATIONS.items()}
        for filename, required in FILES.items():
            r = {"fileName": filename, "processedRows": 0, "importedRows": 0, "skippedRows": 0, "invalidRows": 0,
                 "observationValuesInserted": 0, "missingValues": 0, "conflictingValues": 0, "warnings": [], "errors": [],
                 "dateStart": None, "dateEnd": None, "locations": [], "sha256": hashes[filename]}
            report["files"].append(r)
            dates, seen, pending = [], set(), defaultdict(list)
            try:
                headers, rows = read_csv(IMPORT_DIR / filename, required)
                r["headers"] = headers
                climate_parameters = [p for p in PARAMETERS if p in headers and not p.startswith("GWET")]
                if filename == "nasa_daily.csv":
                    if not climate_parameters:
                        raise ValueError("No recognized climate variables exist")
                    r["warnings"].append("Climate CSV has no coordinates, unit metadata, source URL, retrieval date or time standard. Study coordinates are supplied by the project brief; units are mapped from official NASA POWER parameter metadata, checked 2026-11-14. Original download provenance/time standard cannot be independently verified.")
                if filename == "nasa_monthly.csv":
                    r["warnings"].append("Validation-only derived dataset; daily observations remain authoritative. >35°C uses strict greater-than. Rounding tolerance 0.0011 (means), 0.011 mm (rainfall).")
                for index, row in enumerate(rows, 2):
                    r["processedRows"] += 1
                    try:
                        sid = row["location_id"]
                        if sid not in locations:
                            raise ValueError("Unknown location_id")
                        loc = locations[sid]
                        if sid not in r["locations"]:
                            r["locations"].append(sid)
                        date_text = row.get("date", row.get("month", "static"))
                        unique = (sid, date_text)
                        if unique in seen:
                            raise ValueError("Duplicate location/date row within file")
                        seen.add(unique)
                        if filename == "soilgrids_0_5cm_aligned.csv":
                            _import_soil(db, loc, row, r, hashes[filename])
                            continue
                        day = parse_date(date_text + "-01" if filename == "nasa_monthly.csv" else date_text)
                        dates.append(day.isoformat())
                        if filename == "nasa_monthly.csv":
                            _validate_monthly(db, loc, row, day)
                            r["skippedRows"] += 1
                            continue
                        wet = filename == "nasa_soil_moisture_daily.csv"
                        params = ["GWETTOP", "GWETROOT"] if wet else climate_parameters
                        url = source_url(loc.latitude, loc.longitude, params, wet)
                        if wet:
                            if row["data_classification"] != WETNESS or row["units"] != "fraction of saturation":
                                raise ValueError("Wetness classification/units do not match NASA definitions")
                            parsed = urlparse(row["source_url"])
                            query = parse_qs(parsed.query)
                            if parsed.hostname != "power.larc.nasa.gov" or parsed.scheme != "https":
                                raise ValueError("Unrecognized NASA source URL")
                            lat, lon = coords(query["latitude"][0], query["longitude"][0])
                            if abs(lat-loc.latitude) > .00001 or abs(lon-loc.longitude) > .00001:
                                raise ValueError("Source coordinates do not match study reference")
                            if query.get("community") != ["AG"] or query.get("time-standard") != ["UTC"]:
                                raise ValueError("Unexpected NASA community or time standard")
                            if any(row.get(p, "").strip() for p in ("SFMC", "RZMC")):
                                raise ValueError("Unexpected volumetric moisture values; not a SMAP dataset")
                            url = row["source_url"]
                        records = []
                        for p in params:
                            value, quality = numeric(row[p], p)
                            r["missingValues"] += int(value is None)
                            records.append(dict(location_key=loc.key, date=day, parameter=p, value=value,
                                unit=PARAMETERS[p][0], source="NASA POWER", product="POWER_DAILY",
                                source_url=url, classification=WETNESS if wet else CLIMATE, quality=quality,
                                retrieved_at=started, metadata_json={"file": filename, "sha256": hashes[filename],
                                "originalRetrievalDate": None, "unitMetadataUrl": METADATA_URL, "unitVerification": "official_parameter_definitions_not_embedded_metadata",
                                "timeStandard": "UTC" if wet else "unspecified_in_uploaded_file", "sourceUrlKind": "original" if wet else "reconstructed_from_brief"}))
                        pending[sid].append((index, records))
                    except (ValueError, KeyError, TypeError, OverflowError) as exc:
                        r["invalidRows"] += 1
                        if len(r["errors"]) < 40:
                            r["errors"].append(f"Row {index}: {exc}")
                for sid, batches in pending.items():
                    records = [v for _, group in batches for v in group]
                    # Report source rows by comparing each row to the immutable stored values.
                    existing = {(v.date, v.parameter): v for v in db.scalars(select(EnvironmentalValue).where(EnvironmentalValue.location_key == locations[sid].key))}
                    for index, group in batches:
                        conflicts = [v for v in group if (v["date"], v["parameter"]) in existing and
                            (existing[(v["date"], v["parameter"])].value != v["value"] or existing[(v["date"], v["parameter"])].unit != v["unit"])]
                        if conflicts:
                            r["invalidRows"] += 1
                            r["conflictingValues"] += len(conflicts)
                            if len(r["errors"]) < 40:
                                r["errors"].append(f"Row {index}: conflicting stored observations; existing values retained")
                        elif all((v["date"], v["parameter"]) in existing for v in group):
                            r["skippedRows"] += 1
                        else:
                            r["importedRows"] += 1
                    # Conflicting rows are excluded in their entirety.
                    safe = [v for _, group in batches if not any((v["date"], v["parameter"]) in existing and
                        existing[(v["date"], v["parameter"])].value != v["value"] for v in group) for v in group]
                    inserted, _, conflict_count = store_values(db, safe)
                    r["observationValuesInserted"] += inserted
                db.flush()
                if dates:
                    r["dateStart"], r["dateEnd"] = min(dates), max(dates)
                if r["locations"] != [] and set(r["locations"]) != set(LOCATIONS):
                    r["warnings"].append("Not all four study locations are present")
                if filename in {"nasa_daily.csv", "nasa_soil_moisture_daily.csv"} and len(rows) != 10228:
                    r["warnings"].append("Expected 10,228 location-days for complete four-location 2019–2025 coverage")
            except (ValueError, OSError, csv.Error) as exc:
                r["errors"].append(str(exc))
            r["status"] = "failed" if r["errors"] else "validated_with_warnings" if r["warnings"] or r["missingValues"] else "validated"
        report["warnings"].append("Imported row counts count CSV source rows, not parameter cells. Monthly CSV rows are validation-only (skipped); values are recalculated from daily records. Ingestion timestamps are not original NASA download dates.")
        report["completedAt"] = datetime.now(timezone.utc).isoformat()
        audit.status = "partial" if any(f["errors"] for f in report["files"]) else "completed"
        audit.report, audit.completed_at = report, datetime.now(timezone.utc)
        db.commit()
        return {"id": audit.id, "status": audit.status, **report}


def _validate_monthly(db, loc, row, day):
    import statistics
    values = list(db.scalars(select(EnvironmentalValue).where(EnvironmentalValue.location_key == loc.key,
        EnvironmentalValue.date >= day, EnvironmentalValue.date <= day.replace(day=calendar.monthrange(day.year, day.month)[1]))))
    by_parameter = defaultdict(list)
    for v in values:
        if v.value is not None:
            by_parameter[v.parameter].append(v.value)
    expected = {"temp_mean_c": statistics.mean(by_parameter["T2M"]) if by_parameter["T2M"] else None,
        "rain_total_mm": sum(by_parameter["PRECTOTCORR"]) if by_parameter["PRECTOTCORR"] else None,
        "humidity_mean_pct": statistics.mean(by_parameter["RH2M"]) if by_parameter["RH2M"] else None,
        "days_max_over_35c": sum(x > 35 for x in by_parameter["T2M_MAX"]),
        "temp_valid_days": len(by_parameter["T2M"]), "rain_valid_days": len(by_parameter["PRECTOTCORR"]),
        "days_in_month": calendar.monthrange(day.year, day.month)[1]}
    for key, calculated in expected.items():
        supplied = None if row[key] == "" else float(row[key])
        tolerance = .011 if key == "rain_total_mm" else .0011 if "mean" in key else 0
        if supplied is None and calculated is None:
            continue
        if supplied is None or calculated is None or not math.isfinite(supplied) or abs(supplied-calculated) > tolerance:
            raise ValueError(f"Monthly cross-check failed for {key}: supplied={supplied}, calculated={calculated}")


def _import_soil(db, loc, row, report, sha):
    lat, lon = coords(row["original_latitude"], row["original_longitude"])
    slat, slon = coords(row["sample_latitude"], row["sample_longitude"])
    if abs(lat-loc.latitude) > .00001 or abs(lon-loc.longitude) > .00001:
        raise ValueError("Soil original coordinates do not match study reference")
    if row["status"] != "PROXY_DEMO_ONLY" or row["depth_cm"] != "0-5" or row["sample_status"] != "NEARBY_PROXY_NOT_FARM_VALIDATED":
        raise ValueError("Incorrect soil classification or depth")
    if row["classification"] != "modeled_250m_soil_prediction_not_field_test" or row["error"]:
        raise ValueError("Soil record has classification or quality errors")
    offset = float(row["offset_km"])
    delta_lat, delta_lon = math.radians(slat-lat), math.radians(slon-lon)
    a = math.sin(delta_lat/2)**2 + math.cos(math.radians(lat))*math.cos(math.radians(slat))*math.sin(delta_lon/2)**2
    distance = 6371 * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    if not math.isfinite(offset) or offset < 0:
        raise ValueError("Invalid sampling distance")
    distance_warning = None
    if abs(distance-offset) > max(.05, offset*.03):
        distance_warning = f"{row['location_id']}: source distance {offset:.3f} km differs from coordinate-derived haversine distance {distance:.3f} km. Both are retained; proxy quality flagged."
        report["warnings"].append(distance_warning)
    properties = soil_values(row)
    report["missingValues"] += sum(p["value"] is None for p in properties.values())
    texture = [properties[k]["value"] for k in ("clay_pct", "sand_pct", "silt_pct")]
    if all(x is not None for x in texture) and abs(float(row["texture_sum_pct"])-sum(texture)) > .11:
        raise ValueError("Reported texture total does not match component values")
    existing = db.scalar(select(SoilEstimate).where(SoilEstimate.location_key == loc.key))
    if existing:
        if (existing.properties != properties or existing.sample_latitude != slat or existing.sample_longitude != slon
                or existing.offset_km != offset or existing.classification != row["status"]):
            raise ValueError("Conflicting soil estimate exists; retained without overwrite")
        report["skippedRows"] += 1
        return
    db.add(SoilEstimate(location_key=loc.key, original_latitude=lat, original_longitude=lon,
        sample_latitude=slat, sample_longitude=slon, offset_km=offset, depth_cm="0-5",
        classification=row["status"], properties=properties, provenance={
            "source": row["source"], "sourceUrl": "https://soilgrids.org/", "sourceUrlKind": "provider_homepage_not_original_query",
            "quality": "distance_discrepancy" if distance_warning else row["sample_status"],
            "calculatedOffsetKm": distance, "distanceWarning": distance_warning,
            "classification": row["classification"], "textureQuality": row["texture_quality"],
            "file": "soilgrids_0_5cm_aligned.csv", "sha256": sha, "originalRetrievalDate": None,
            "warning": "Original SoilGrids query URL and retrieval date were not included in the CSV. Never use as ground-truth labels."}))
    report["importedRows"] += 1
    report["observationValuesInserted"] += len(properties)


def import_bundle(path=DEFAULT_ZIP):
    try:
        return _import_bundle(path)
    except Exception:
        import logging
        logging.getLogger(__name__).exception("Environmental bundle import failed; transaction rolled back")
        report = {"errors": ["Import failed because of a database or unexpected processing error. No uncommitted values were saved. See server logs."], "files": []}
        with SessionLocal() as db:
            audit = IngestionReport(source=Path(path).name, status="failed", completed_at=datetime.now(timezone.utc), report=report)
            db.add(audit)
            db.commit()
            return {"id": audit.id, "status": audit.status, **report}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", default=str(DEFAULT_ZIP))
    args = parser.parse_args()
    print(json.dumps(import_bundle(args.zip), indent=2))
