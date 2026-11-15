import os
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Request, Query, HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import EnvironmentalLocation, EnvironmentalValue, FarmerMeasurement, IngestionReport, SoilEstimate
from ..schemas import MeasurementInput
from .power_client import ensure_environment
from .service import summary_for, soil_for, location_json, observation_rows
from .calculations import daily_rows
from .constants import LOCATIONS, location_key
from .importer import import_bundle
from .features import build_features
from .storage import ensure_location

router = APIRouter(prefix="/api")


def point(latitude: float = Query(ge=-90, le=90, allow_inf_nan=False),
          longitude: float = Query(ge=-180, le=180, allow_inf_nan=False), db: Session = Depends(get_db)):
    return ensure_environment(db, latitude, longitude)


@router.get("/environment/summary")
def summary(location=Depends(point), hot_threshold: float = Query(35, ge=-20, le=60),
            dry_threshold: float = Query(1, ge=0, le=100), db: Session = Depends(get_db)):
    return summary_for(db, location, hot_threshold, dry_threshold)


@router.get("/environment/history")
def history(location=Depends(point), year: int = Query(2025, ge=2019, le=2025), db: Session = Depends(get_db)):
    rows = daily_rows(observation_rows(db, location))
    return {"location": location_json(location), "year": year, "daily": [r for r in rows if r["date"].startswith(str(year))],
        "units": {"T2M": "C", "T2M_MAX": "C", "T2M_MIN": "C", "PRECTOTCORR": "mm/day", "RH2M": "%", "GWETTOP": "1", "GWETROOT": "1"},
        "warning": "NASA POWER gridded estimates. Wetness is modeled, not SMAP or volumetric moisture. Missing days remain gaps."}


@router.get("/environment/soil-wetness")
def wetness(location=Depends(point), db: Session = Depends(get_db)):
    summary = summary_for(db, location)
    return {"location": summary["location"], "monthly": summary["monthly"], "seasonal": summary["seasonal"],
        "classification": "NASA_POWER_WETNESS_FRACTION_NOT_SMAP", "unit": "1", "warnings": summary["warnings"]}


@router.get("/environment/soil-properties")
def soil(latitude: float = Query(ge=-90, le=90, allow_inf_nan=False),
         longitude: float = Query(ge=-180, le=180, allow_inf_nan=False), db: Session = Depends(get_db)):
    location = ensure_location(db, latitude, longitude)
    # Independent of NASA availability; read-only proxy lookup never calls NASA.
    return soil_for(db, location)


@router.get("/environment/compare")
def compare(db: Session = Depends(get_db)):
    result = []
    for id, (name, lat, lon) in LOCATIONS.items():
        location = db.get(EnvironmentalLocation, location_key(lat, lon))
        result.append({"studyId": id, "name": name, "latitude": lat, "longitude": lon,
            "summary": summary_for(db, location) if location else None})
    return result


@router.get("/data/status")
def status(db: Session = Depends(get_db)):
    audits = db.scalars(select(IngestionReport).order_by(IngestionReport.id.desc()).limit(15)).all()
    return {"environmentalValues": db.scalar(select(func.count()).select_from(EnvironmentalValue)),
        "soilEstimates": db.scalar(select(func.count()).select_from(SoilEstimate)),
        "importPolicy": "Only operator-allowlisted browser sessions may run the fixed-bundle import. Server CLI is available; arbitrary uploads/paths are not accepted.",
        "reports": [{"id": a.id,
                     "source": "NASA POWER API (requested coordinates withheld)" if a.source.startswith("NASA POWER API ") else a.source,
                     "status": a.status, "startedAt": a.started_at.isoformat(),
                     "completedAt": a.completed_at.isoformat() if a.completed_at else None,
                     "report": {k: v for k, v in a.report.items() if k not in {"latitude", "longitude"}}
                     if a.source.startswith("NASA POWER API ") else a.report} for a in audits]}


@router.post("/data/import")
def run_import(request: Request):
    from ..main import owner
    admins = {v.strip() for v in os.environ.get("FIELD_SHIFT_IMPORT_OPERATORS", "").split(",") if v.strip()}
    if owner(request) not in admins:
        raise HTTPException(403, "Dataset imports are restricted to server operators. Use the documented server CLI; public sessions cannot import data.")
    return import_bundle()


def measurement_json(m):
    return {"id": m.id, "farmId": m.farm_id, "parameter": m.parameter, "value": m.value, "unit": m.unit,
        "depthTopCm": m.depth_top_cm, "depthBottomCm": m.depth_bottom_cm, "measuredOn": m.measured_on.isoformat(),
        "source": m.source, "notes": m.notes, "createdAt": m.created_at.isoformat(),
        "verification": "Farmer-reported laboratory result; not independently verified" if m.source == "laboratory_confirmed" else "Farmer-reported; unverified"}


@router.get("/farms/{id}/measurements")
def measurements(id: int, request: Request, db: Session = Depends(get_db)):
    from ..main import owner, find_farm
    find_farm(id, owner(request), db)
    return [measurement_json(m) for m in db.scalars(select(FarmerMeasurement).where(FarmerMeasurement.farm_id == id).order_by(FarmerMeasurement.measured_on.desc(), FarmerMeasurement.id.desc()))]


@router.post("/farms/{id}/measurements", status_code=201)
def save_measurement(id: int, data: MeasurementInput, request: Request, db: Session = Depends(get_db)):
    from ..main import owner, find_farm
    farm = find_farm(id, owner(request), db)
    # Serialize composition validation for entries in the same farm/date/depth.
    db.scalar(select(type(farm)).where(type(farm).id == id).with_for_update())
    if data.parameter in {"clay_pct", "sand_pct", "silt_pct"}:
        prior = db.scalars(select(FarmerMeasurement).where(FarmerMeasurement.farm_id == id,
            FarmerMeasurement.measured_on == data.measuredOn, FarmerMeasurement.source == data.source,
            FarmerMeasurement.depth_top_cm == data.depthTopCm,
            FarmerMeasurement.depth_bottom_cm == data.depthBottomCm).order_by(FarmerMeasurement.id.desc())).all()
        parts = {data.parameter: data.value}
        for p in prior:
            if p.parameter in {"clay_pct", "sand_pct", "silt_pct"}:
                parts.setdefault(p.parameter, p.value)
        if len(parts) == 3 and abs(sum(parts.values())-100) > 1:
            raise HTTPException(422, "Clay, sand and silt for the same date/depth/source must total approximately 100%. Existing entries were retained.")
    m = FarmerMeasurement(farm_id=id, parameter=data.parameter, value=data.value, unit=data.unit,
        depth_top_cm=data.depthTopCm, depth_bottom_cm=data.depthBottomCm, measured_on=data.measuredOn,
        source=data.source, notes=data.notes)
    db.add(m)
    db.commit()
    db.refresh(m)
    return measurement_json(m)


@router.get("/farms/{id}/features")
def features(id: int, request: Request, db: Session = Depends(get_db)):
    from ..main import owner, find_farm
    farm = find_farm(id, owner(request), db)
    location = ensure_environment(db, farm.profile["latitude"], farm.profile["longitude"])
    return build_features(db, farm, location)
