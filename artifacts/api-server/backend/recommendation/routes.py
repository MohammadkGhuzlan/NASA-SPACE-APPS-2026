from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import RecommendationResult, Strategy
from ..environment.power_client import ensure_environment
from ..environment.service import summary_for
from ..environment.features import build_features
from .schemas import FarmingPlanInput
from .knowledge import library, resolve
from .engine import build_report
from ..analysis.model import model_status
from ..analysis.service import integrate_report
from ..analysis.limits import check_analysis_rate

router = APIRouter(prefix="/api")


@router.get("/analysis/model-status")
def analysis_model_status():
    return model_status()


@router.get("/knowledge")
def knowledge():
    return library()


def owned_farm(id, request, db):
    from ..main import owner, find_farm
    return find_farm(id, owner(request), db)


@router.get("/farms/{id}/plans")
def list_plans(id: int, request: Request, db: Session = Depends(get_db)):
    owned_farm(id, request, db)
    rows = db.scalars(select(RecommendationResult).where(
        RecommendationResult.farm_id == id).order_by(RecommendationResult.id.desc())).all()
    return [{"id": r.id, "farmId": id, "createdAt": r.created_at.isoformat(),
             "status": r.result.get("status", "unavailable"),
             "knowledgeVersion": r.result.get("knowledgeVersion", "unknown")} for r in rows]


@router.get("/farms/{id}/plans/{planId}")
def get_plan(id: int, planId: int, request: Request, db: Session = Depends(get_db)):
    owned_farm(id, request, db)
    row = db.scalar(select(RecommendationResult).where(
        RecommendationResult.id == planId, RecommendationResult.farm_id == id))
    if not row:
        raise HTTPException(404, "Planning report not found in this farm workspace")
    return {**row.result, "id": row.id}


@router.post("/farms/{id}/plans", status_code=201)
def generate(id: int, data: FarmingPlanInput, request: Request, db: Session = Depends(get_db)):
    farm = owned_farm(id, request, db)
    unknown = [n for n in data.excludedCrops if resolve(n) is None]
    if unknown:
        raise HTTPException(422, "Excluded crops must match library crops: " + ", ".join(unknown))
    from ..main import owner
    check_analysis_rate(owner(request))
    location = ensure_environment(db, farm.profile["latitude"], farm.profile["longitude"])
    summary = summary_for(db, location)
    features = build_features(db, farm, location)
    drafts = db.scalars(select(Strategy).where(Strategy.farm_id == id)).all()
    result = build_report(farm, data, summary, features, drafts)
    result = integrate_report(farm, data, summary, features, result)
    row = RecommendationResult(farm_id=id, model_id=None, strategy_id=None, result=result)
    db.add(row)
    db.commit()
    db.refresh(row)
    return {**result, "id": row.id}
