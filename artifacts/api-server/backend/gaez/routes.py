from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..recommendation.routes import owned_farm
from .catalog import catalog_status
from .sampling import assess

router = APIRouter(prefix="/api")


class GaezInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    cropCode: str = Field(min_length=1, max_length=10)
    scenario: str = Field(min_length=1, max_length=10)
    datasetVersion: str = Field(default="GAEZ-v5", max_length=20)
    referencePeriod: str = Field(default="2001-2020", max_length=20)


@router.get("/gaez/catalog")
def catalog():
    return catalog_status()


@router.post("/farms/{id}/gaez")
def assessment(id: int, data: GaezInput, request: Request, db: Session = Depends(get_db)):
    farm = owned_farm(id, request, db)
    result = assess(farm.profile["latitude"], farm.profile["longitude"], data.cropCode, data.scenario,
                    version=data.datasetVersion, period=data.referencePeriod)
    if data.scenario in {"LILM", "HILM"}:
        irrigation = farm.profile.get("irrigation", "unknown")
        result["warnings"].append(
            f"Farmer-reported irrigation: {irrigation}. Both LILM and HILM assume irrigation; "
            "limited or unquantified water does not establish that this scenario is feasible. "
            "Confirm seasonal water volume and restrictions before considering it.")
    if data.scenario in {"HILM", "HRLM"}:
        result["warnings"].append("High input management is an assessment assumption, not a verified farm capability.")
    return result
