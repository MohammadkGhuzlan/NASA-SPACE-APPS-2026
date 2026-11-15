import logging
import os
import secrets
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from uuid import uuid4
import httpx
from fastapi import FastAPI, Depends, HTTPException, Request, Query
from fastapi.responses import JSONResponse
from sqlalchemy import select, delete
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware
from .database import get_db, SessionLocal
from .catalog import ensure_source_registry
from .models import Farm, Strategy, DataSource, Observation
from .schemas import FarmInput, StrategyInput
from .data_ingestion.power import fetch_environment

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("field_shift")
@asynccontextmanager
async def lifespan(app):
    # Data-only, idempotent reference seed. Schema is NEVER changed at startup.
    with SessionLocal() as db:
        ensure_source_registry(db)
        from .recommendation.knowledge import ensure_knowledge
        ensure_knowledge(db)
    yield


app = FastAPI(title="Field Shift", docs_url="/api/docs", openapi_url="/api/openapi.json", lifespan=lifespan)
app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ["SESSION_SECRET"],
    session_cookie="field_shift_session", same_site="lax",
    https_only=os.environ.get("NODE_ENV") == "production",
    max_age=60 * 60 * 24 * 365,
)


@app.middleware("http")
async def protect_requests(request: Request, call_next):
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        if request.headers.get("sec-fetch-site") == "cross-site":
            return JSONResponse({"error": "Cross-site writes are not permitted."}, status_code=403)
        try:
            size = int(request.headers.get("content-length", "0"))
        except ValueError:
            return JSONResponse({"error": "Invalid request length."}, status_code=400)
        if size > 100_000:
            return JSONResponse({"error": "Request too large."}, status_code=413)
    try:
        return await call_next(request)
    except Exception:
        logger.exception("Request failed")
        return JSONResponse({"error": "The server could not complete this request. Please retry."}, status_code=500)


def owner(request: Request):
    if "owner" not in request.session:
        request.session["owner"] = str(uuid4())
    return request.session["owner"]


def find_farm(id: int, owner_id: str, db: Session):
    farm = db.scalar(select(Farm).where(Farm.id == id, Farm.owner == owner_id))
    if not farm:
        raise HTTPException(404, "Farm not found in this browser workspace.")
    return farm


def farm_json(farm):
    profile = {k: v for k, v in farm.profile.items() if v is not None or k != "boundary"}
    return {**profile, "id": farm.id, "createdAt": farm.created_at.isoformat(), "updatedAt": farm.updated_at.isoformat()}


@app.get("/api/healthz")
def health():
    return {"status": "ok"}


@app.get("/api/farms")
def list_farms(request: Request, db: Session = Depends(get_db)):
    farms = db.scalars(select(Farm).where(Farm.owner == owner(request)).order_by(Farm.updated_at.desc())).all()
    return [farm_json(f) for f in farms]


@app.post("/api/farms", status_code=201)
def create_farm(data: FarmInput, request: Request, db: Session = Depends(get_db)):
    farm = Farm(owner=owner(request), profile=data.model_dump(exclude_none=True))
    db.add(farm)
    db.commit()
    db.refresh(farm)
    return farm_json(farm)


@app.get("/api/farms/{id}")
def get_farm(id: int, request: Request, db: Session = Depends(get_db)):
    return farm_json(find_farm(id, owner(request), db))


@app.put("/api/farms/{id}")
def update_farm(id: int, data: FarmInput, request: Request, db: Session = Depends(get_db)):
    farm = find_farm(id, owner(request), db)
    changed = (farm.profile["latitude"], farm.profile["longitude"]) != (data.latitude, data.longitude)
    farm.profile = data.model_dump(exclude_none=True)
    farm.updated_at = datetime.now(timezone.utc)
    if changed:
        db.execute(delete(Observation).where(Observation.farm_id == id))
    db.commit()
    db.refresh(farm)
    return farm_json(farm)


CASE_STUDIES = [
    {"name": "Irbid, Jordan", "latitude": 32.55696, "longitude": 35.84790, "country": "Jordan", "description": "Regional reference, not a validated farm center."},
    {"name": "Al Ain, Abu Dhabi, UAE", "latitude": 24.2249, "longitude": 55.7452, "country": "United Arab Emirates", "description": "Regional reference, not a validated farm center."},
    {"name": "Colusa, California, USA", "latitude": 39.2146, "longitude": -122.0094, "country": "United States", "description": "Regional reference, not a validated farm center."},
    {"name": "Stuttgart, Arkansas, USA", "latitude": 34.5004, "longitude": -91.5526, "country": "United States", "description": "Explore the Arkansas Grand Prairie. A geographic starting point only."},
]


@app.get("/api/case-studies")
def case_studies():
    return CASE_STUDIES


geocode_lock = threading.Lock()
geocode_last_call = 0.0
geocode_cache = {}


@app.get("/api/geocode")
def geocode(q: str = Query(min_length=2, max_length=150)):
    global geocode_last_call
    q = q.strip()
    if len(q) < 2:
        raise HTTPException(422, "Enter at least two characters.")
    key = q.casefold()
    with geocode_lock:
        if key in geocode_cache:
            return geocode_cache[key]
        if time.monotonic() - geocode_last_call < 1.05:
            raise HTTPException(429, "Please wait a moment before searching again.")
        geocode_last_call = time.monotonic()
        try:
            with httpx.Client(timeout=12) as client:
                result = client.get("https://nominatim.openstreetmap.org/search", params={"q": q, "format": "jsonv2", "limit": 5, "addressdetails": 1}, headers={"User-Agent": "FieldShift/0.1 (NASA Space Apps educational farm planning prototype)"})
                result.raise_for_status()
                rows = result.json()
            mapped = [{"name": r["display_name"], "latitude": float(r["lat"]), "longitude": float(r["lon"]), "country": r.get("address", {}).get("country", ""), "description": "OpenStreetMap / Nominatim search result"} for r in rows]
            if len(geocode_cache) > 250:
                geocode_cache.clear()
            geocode_cache[key] = mapped
            return mapped
        except (httpx.HTTPError, ValueError, KeyError):
            raise HTTPException(503, "Location search is unavailable. Choose a point on the map or enter coordinates.")


@app.get("/api/farms/{id}/environment")
def environment(id: int, request: Request, db: Session = Depends(get_db)):
    farm = find_farm(id, owner(request), db)
    from .environment.power_client import ensure_environment
    from .environment.service import summary_for
    location = ensure_environment(db, farm.profile["latitude"], farm.profile["longitude"])
    result = summary_for(db, location)
    months = [m for m in result["monthly"] if m["period"].startswith("2025")]
    import calendar
    return {"status": result["status"], "source": "NASA POWER", "sourceUrl": "https://power.larc.nasa.gov/",
        "dateRange": "2025-01-01 to 2025-12-31",
        "monthly": [{"month": calendar.month_abbr[int(m["period"][-2:])], "temperature": m["T2M"], "rainfall": m["PRECTOTCORR"]} for m in months],
        "heatDays": result["annual"][-1]["hotDays35"], "soilMoisture": None, "vegetationIndex": None,
        "fetchedAt": result["provenance"][0]["retrievedAt"] if result["provenance"] else None, "warnings": result["warnings"]}


def strategy_json(s):
    return {"id": s.id, "farmId": s.farm_id, "slot": s.slot, "name": s.name, "crops": s.crops, "notes": s.notes, "status": s.status}


@app.get("/api/farms/{id}/strategies")
def strategies(id: int, request: Request, db: Session = Depends(get_db)):
    find_farm(id, owner(request), db)
    return [strategy_json(s) for s in db.scalars(select(Strategy).where(Strategy.farm_id == id).order_by(Strategy.slot)).all()]


@app.post("/api/farms/{id}/strategies", status_code=201)
def save_strategy(id: int, data: StrategyInput, request: Request, db: Session = Depends(get_db)):
    # Serialize updates to each farm's two draft slots.
    farm = find_farm(id, owner(request), db)
    db.scalar(select(Farm).where(Farm.id == farm.id).with_for_update())
    strategy = db.scalar(select(Strategy).where(Strategy.farm_id == id, Strategy.slot == data.slot))
    if strategy is None:
        strategy = Strategy(farm_id=id, **data.model_dump(), status="unassessed_draft")
        db.add(strategy)
    else:
        for key, value in data.model_dump().items():
            setattr(strategy, key, value)
    db.commit()
    db.refresh(strategy)
    return strategy_json(strategy)


@app.get("/api/sources")
def sources(db: Session = Depends(get_db)):
    return [{"id": s.id, "name": s.name, "url": s.url, "status": s.status, "description": s.description} for s in db.scalars(select(DataSource).order_by(DataSource.id)).all()]


from .environment.routes import router as environmental_router
app.include_router(environmental_router)
from .recommendation.routes import router as planning_router
app.include_router(planning_router)
from .gaez.routes import router as gaez_router
app.include_router(gaez_router)
