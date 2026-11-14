"""Server-only NASA POWER client. TLS verification stays enabled."""
import hashlib
import logging
import time
import threading
from collections import deque
from datetime import datetime, timezone, timedelta
import httpx
from sqlalchemy import select, text, func
from ..models import EnvironmentalValue, EnvironmentalLocation, IngestionReport
from .constants import PARAMETERS, POWER_URL, CLIMATE, WETNESS, START, END
from .validation import numeric, parse_date, coords
from .storage import ensure_location, store_values

logger = logging.getLogger(__name__)
requests_lock = threading.Lock()
request_times = deque()
request_slots = threading.BoundedSemaphore(2)


def parse_response(payload, requested, location, url):
    header = payload["header"]
    if header.get("time_standard") != "UTC":
        raise ValueError("NASA response has unexpected time standard")
    metadata = payload["parameters"]
    values = payload["properties"]["parameter"]
    records, warnings = [], []
    retrieved = datetime.now(timezone.utc)
    for p in requested:
        if p not in values or p not in metadata:
            warnings.append(f"NASA did not return {p}; it remains unavailable.")
            continue
        if metadata[p].get("units") != PARAMETERS[p][0]:
            warnings.append(f"{p}: unexpected units; variable rejected.")
            continue
        for raw_date, raw_value in values[p].items():
            try:
                day = parse_date(datetime.strptime(raw_date, "%Y%m%d").date().isoformat())
                value, quality = numeric(raw_value, p, header.get("fill_value", -999))
            except (ValueError, TypeError):
                warnings.append(f"{p} {raw_date}: invalid measurement rejected")
                continue
            records.append(dict(location_key=location.key, date=day, parameter=p, value=value,
                unit=metadata[p]["units"], source="NASA POWER", product="POWER_DAILY",
                source_url=url, classification=WETNESS if p.startswith("GWET") else CLIMATE,
                quality=quality, retrieved_at=retrieved, metadata_json={
                    "header": header, "parameterMetadata": metadata[p],
                    "returnedGeometry": payload.get("geometry"), "requestedCoordinates": [location.longitude, location.latitude],
                    "timeStandard": "UTC", "sourceUrlKind": "original_live_request"}))
    if not records:
        raise ValueError("No valid NASA variables were returned")
    return records, list(dict.fromkeys(warnings))[:50]


def request_group(client, lat, lon, parameters):
    params = {"parameters": ",".join(parameters), "community": "AG", "latitude": lat,
              "longitude": lon, "start": "20190101", "end": "20251231",
              "format": "JSON", "time-standard": "UTC"}
    for attempt in range(2):
        try:
            response = client.get(POWER_URL, params=params)
            if response.status_code == 422:
                raise ValueError("NASA rejected these coordinates or variables (HTTP 422). No substitute product was used.")
            response.raise_for_status()
            return response.json(), str(response.url)
        except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
            retryable = not isinstance(exc, httpx.HTTPStatusError) or exc.response.status_code in (429, 500, 502, 503, 504)
            if attempt or not retryable:
                raise
            time.sleep(.7)


def ensure_environment(db, lat, lon):
    coords(lat, lon)
    location = ensure_location(db, lat, lon)
    count = db.scalar(select(func.count()).select_from(EnvironmentalValue).where(EnvironmentalValue.location_key == location.key))
    def fresh():
        if count and (location.study_id or (not location.last_error and location.last_attempt and location.last_attempt > datetime.now(timezone.utc)-timedelta(days=30))):
            return True
        return bool(location.last_attempt and location.last_attempt > datetime.now(timezone.utc)-timedelta(minutes=3))
    # Cached reads need no exclusive lock. Summary/history/wetness load in parallel.
    if fresh():
        return location
    # DB advisory lock works across API workers; exact point cache, never nearest city.
    lock = int(hashlib.sha256(location.key.encode()).hexdigest()[:15], 16)
    from fastapi import HTTPException
    if not db.scalar(text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": lock}):
        raise HTTPException(409, "Data for this point is already being retrieved. Please retry in a moment.")
    db.refresh(location)
    count = db.scalar(select(func.count()).select_from(EnvironmentalValue).where(EnvironmentalValue.location_key == location.key))
    # Historical uploaded observations are immutable; imported coverage served directly.
    if fresh():
        return location
    with requests_lock:
        now = time.monotonic()
        while request_times and now-request_times[0] > 60:
            request_times.popleft()
        if len(request_times) >= 12 or not request_slots.acquire(blocking=False):
            raise HTTPException(429, "The environmental service is busy. Please wait a minute before requesting a new location.")
        request_times.append(now)
    location.last_attempt = datetime.now(timezone.utc)
    errors, warnings, inserted = [], [], 0
    audit = IngestionReport(source=f"NASA POWER API {location.key}", status="running", report={})
    db.add(audit)
    # Bounded two attempts per product group, climate still works if wetness fails.
    try:
        with httpx.Client(timeout=httpx.Timeout(25, connect=8), headers={"User-Agent": "FieldShift/0.2"}) as client:
            for group in (["T2M", "T2M_MAX", "T2M_MIN", "PRECTOTCORR", "RH2M"], ["GWETTOP", "GWETROOT"]):
                try:
                    payload, url = request_group(client, lat, lon, group)
                    records, notices = parse_response(payload, group, location, url)
                    n, skipped, conflicts = store_values(db, records)
                    inserted += n
                    warnings.extend(notices)
                    if conflicts:
                        warnings.append(f"{conflicts} conflicting observations retained unchanged.")
                except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
                    reason = str(exc) if isinstance(exc, ValueError) else "NASA POWER temporarily unavailable (timeout, network or HTTP error)."
                    errors.append(f"{','.join(group)}: {reason}")
    finally:
        request_slots.release()
    location.last_error = "; ".join(errors) or None
    location.metadata_json = {"warnings": warnings, "cachePolicy": "exact coordinates to 5 decimals; no inferred grid reuse"}
    audit.status = "partial" if errors and inserted else "failed" if errors else "completed"
    audit.report = {"insertedValues": inserted, "errors": errors, "warnings": warnings, "latitude": lat, "longitude": lon}
    audit.completed_at = datetime.now(timezone.utc)
    db.commit()
    return location
