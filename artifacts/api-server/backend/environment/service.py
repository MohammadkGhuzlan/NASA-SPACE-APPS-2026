from sqlalchemy import select
from ..models import EnvironmentalValue, SoilEstimate
from .calculations import daily_rows, summarize
from .constants import SOIL_NOTICE, PARAMETERS
from .power_client import ensure_environment


def observation_rows(db, location):
    return list(db.scalars(select(EnvironmentalValue).where(EnvironmentalValue.location_key == location.key).order_by(EnvironmentalValue.date, EnvironmentalValue.parameter)))


def summary_for(db, location, hot=35, dry=1):
    values = observation_rows(db, location)
    result = summarize(daily_rows(values), hot, dry)
    provenance = {}
    for v in values:
        key = (v.parameter, v.source_url)
        if key not in provenance:
            provenance[key] = {"parameter": v.parameter, "unit": v.unit, "source": v.source,
                "product": v.product, "classification": v.classification, "sourceUrl": v.source_url,
                "retrievedAt": v.retrieved_at.isoformat(), "metadata": v.metadata_json}
    result.update(location=location_json(location), status="available" if values else "unavailable",
        provenance=list(provenance.values()), availableParameters=sorted({v.parameter for v in values if v.value is not None}))
    if any(v.value is None for v in values) or (values and any(m[p] is None for m in result["monthly"] for p in PARAMETERS)):
        result["status"] = "partial"
        result["warnings"].append("Missing or fill-marked daily values exist; incomplete aggregates are shown as gaps.")
    if location.last_error:
        result["warnings"].append(location.last_error)
    result["warnings"].extend(location.metadata_json.get("warnings", []))
    if any(v.metadata_json.get("timeStandard") == "unspecified_in_uploaded_file" for v in values):
        result["warnings"].append("Uploaded climate CSV time standard and original retrieval date are unspecified. Climate/wetness daily alignment is not independently verified. Units were checked against official NASA definitions, not embedded file metadata.")
    return result


def location_json(location):
    return {"key": location.key, "name": location.name, "latitude": location.latitude, "longitude": location.longitude,
        "studyId": location.study_id, "matchingPolicy": "Exact requested coordinates (5 decimal places); no nearest-city or unverified grid-cell substitution."}


def soil_for(db, location):
    estimate = db.scalar(select(SoilEstimate).where(SoilEstimate.location_key == location.key))
    if not estimate:
        return {"status": "unavailable", "notice": SOIL_NOTICE, "estimate": None,
                "warnings": ["No soil estimate is stored for these exact reference coordinates. Nearby study-city proxies are never assigned to another farm."]}
    warnings = [estimate.provenance["warning"]]
    if estimate.provenance.get("distanceWarning"):
        warnings.append(estimate.provenance["distanceWarning"])
    return {"status": "proxy_only", "notice": SOIL_NOTICE, "warnings": warnings,
        "estimate": {"originalLatitude": estimate.original_latitude, "originalLongitude": estimate.original_longitude,
            "sampleLatitude": estimate.sample_latitude, "sampleLongitude": estimate.sample_longitude,
            "offsetKm": estimate.offset_km, "depthCm": estimate.depth_cm, "classification": estimate.classification,
            "properties": estimate.properties, "provenance": estimate.provenance,
            "retrievedAt": estimate.retrieved_at.isoformat()}}
