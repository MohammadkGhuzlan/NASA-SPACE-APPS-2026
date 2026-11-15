"""Additional published evidence for Phase 3, not a replacement ranking/model."""
from copy import deepcopy
from datetime import datetime, timezone

from ..recommendation.knowledge import resolve
from .catalog import DATASET, CROPS, SCENARIOS, SourceUnavailable, read_manifest
from .sampling import assess

REFERENCE = {
    "id": "FAO_GAEZ_V5_SIX", "title": "FAO / IIASA GAEZ v5 all-land crop suitability classes",
    "url": DATASET["metadataUrl"],
    "scope": "Published categorical assessment, AgERA5 2001–2020; management-specific, 5 arc minutes; not a farm outcome.",
    "checkedOn": "2026-11-15",
}
ALIASES = {"wheat": ["WHE"], "barley": ["BRL"], "maize": ["MZE"],
           "soybean": ["SOY"], "chickpea": ["CHK"], "rice": ["RCD", "RCW"]}


def codes_for(name):
    # Explicit rice types remain distinct; generic Rice returns BOTH, never a
    # silent wetland default. The planner's own verified aliases are reused.
    if name.strip().casefold() == "gram":
        # The GAEZ catalog has a separate GRM entry; do not reuse Phase 3's
        # ambiguous common-name alias to silently turn it into CHK.
        return []
    for code, label in CROPS.items():
        if name.casefold() in (code.casefold(), label.casefold()):
            return [code]
    crop = resolve(name)
    return ALIASES.get(crop, []) if crop else []


def soil_context(db, farm, location):
    """Retain source depth/date/location, without promoting laboratory claims."""
    from sqlalchemy import select
    from ..models import FarmerMeasurement
    from ..environment.service import soil_for
    from ..environment.routes import measurement_json
    rows = db.scalars(select(FarmerMeasurement).where(
        FarmerMeasurement.farm_id == farm.id).order_by(
            FarmerMeasurement.measured_on.desc(), FarmerMeasurement.id.desc())).all()
    return {"griddedEstimate": soil_for(db, location),
            "farmerMeasurements": [measurement_json(r) for r in rows],
            "farmPoint": {"latitude": farm.profile["latitude"], "longitude": farm.profile["longitude"]},
            "samplingLocationLimit": "Individual sample coordinates are not recorded. Owning farm coordinates are not independently verified sampling coordinates.",
            "verification": "Laboratory-confirmed is a farmer-reported claim, not independently verified."}


def integrate_evidence(farm, planning, summary, features, report, *, soil_provenance=None):
    report = deepcopy(report)
    warnings = [
        "FAO GAEZ is a published modeled assessment, not a trained Field Shift prediction, harvest probability, actual yield or profit.",
        "GAEZ 2001–2020 AgERA5 and NASA POWER 2019–2025 are different source products and periods; no numerical correction is applied.",
        "Class numbers are identifiers, not comparable cross-crop scores; no numeric ranking is derived.",
        "A single 5-arc-minute cell is not an assessment of the whole farm polygon.",
        "Farmer soil claims, laboratory claims, ISRIC/proxy estimates and soil embedded in GAEZ remain distinct; no double-counted independent validation.",
        "FAO describes ECOCROP as a historical database discontinued around 2015. Reference requirements have uneven coverage and are not current local crop trials.",
    ]
    try:
        manifest = read_manifest()
    except SourceUnavailable as exc:
        manifest = None
        warnings.append(str(exc))
    lat, lon = farm.profile["latitude"], farm.profile["longitude"]
    results = ([assess(lat, lon, crop, scenario, manifest=manifest)
                for crop in CROPS for scenario in SCENARIOS] if manifest else [])
    available = [r for r in results if r["status"] == "available"]
    irrigation = farm.profile.get("irrigation", "unknown")
    priority = planning.priority or farm.profile.get("goal", "unknown")
    notes = [
        "FAO evidence adds source-linked candidate explanations and scenario review flags; original Phase 3 option order and three-option comparison are preserved.",
        f"Farmer priority: {priority}; actual water supply, soil tests, management intensity and markets still require local review.",
        "LRLM is an explicit rain-fed/low-input comparison, not an inferred description of this farmer's management.",
    ]
    if irrigation in ("limited", "unknown"):
        notes.append("Limited or unknown irrigation: irrigated HILM/LILM classes are conditional comparators, not feasible recommendations. Confirm actual water volume and input resources.")
    if priority == "conserve_water":
        notes.append("Conserve water: review the rain-fed comparators alongside existing Phase 3 crop-water guidance. No specific irrigation saving follows from a GAEZ class.")
    if any(len(codes_for(n)) > 1 for n in [farm.profile.get("currentCrop", ""), *planning.currentRotation, *planning.previousCrops]):
        warnings.append("Generic Rice does not identify dryland versus wetland production. Both RCD and RCW are shown; the farmer must clarify.")
    by_crop = {}
    for result in results:
        by_crop.setdefault(result["cropCode"], []).append(result)
    for candidate in report.get("candidates", []):
        codes = codes_for(candidate["crop"]["name"])
        if not codes:
            continue
        records = [r for c in codes for r in by_crop.get(c, []) if r["status"] == "available"]
        if records:
            text = "; ".join(f"{r['cropName']} / {r['scenario']}: {r['category']}" for r in records)
            candidate["reasons"].append({"code": "published_fao_assessment",
                "message": text + ". Published class evidence, not a probability or proof of rotation benefit.",
                "sourceIds": [REFERENCE["id"]]})
            if any(r.get("code") == "possible_soil_ph_mismatch" for r in candidate.get("risks", [])):
                candidate["risks"].append({"code": "local_soil_reference_disagreement",
                    "message": "The supplied soil pH raises a local reference conflict. Do not let a coarse FAO assessment override it; verify the measurement and seek local advice.",
                    "sourceIds": [REFERENCE["id"]]})
    for scenario in report.get("scenarios", []):
        for name in dict.fromkeys(scenario["crops"]):
            codes = codes_for(name)
            if not codes:
                notes.append(f"{name}: outside the acquired GAEZ subset, not proven unsuitable.")
            for code in codes:
                r = next((r for r in by_crop.get(code, []) if r["scenario"] == "LRLM"), None)
                if r and r["status"] == "available" and r["rawValue"] in (6, 7, 8):
                    scenario["risks"].append({"code": "fao_rainfed_comparator_review",
                        "message": f"{r['cropName']}: {r['category']} in the published rain-fed/low-input comparator. Review local feasibility; this is not a direction to abandon the crop.",
                        "sourceIds": [REFERENCE["id"]]})
    report["references"] = [*report.get("references", []), REFERENCE,
        {"id": "FAO_ECOCROP_STATUS", "title": "FAO ECOCROP database status and limitations",
         "url": "https://www.fao.org/land-water/resources/tools/databases/ecocrop/en",
         "scope": "Historical crop requirements; discontinued around 2015 and incorporated into GAEZ.",
         "checkedOn": "2026-11-15"}]
    if not available:
        report.setdefault("missingInformation", []).append("No usable published FAO assessment at this point; reference-based planning remains available.")
    snapshot = {
        "status": "available" if len(available) == 28 else "partial" if available else "unavailable",
        "dataset": DATASET, "generatedAt": datetime.now(timezone.utc).isoformat(),
        "results": results, "warnings": warnings,
        "planningNotes": list(dict.fromkeys(notes)),
        "context": {"nasaReferencePeriod": summary.get("referencePeriod"),
                    "nasaProvenance": summary.get("provenance", []),
                    "farmerInputs": {"source": "farmer-provided information", **deepcopy(farm.profile),
                                     "previousCrops": list(planning.previousCrops), "priority": priority},
                    "soilEvidence": deepcopy(features.get("soilInputs", {})),
                    "soilProvenance": deepcopy(soil_provenance),
                    "gaezSoil": "Embedded model assumptions; not new measurements or independent evidence.",
                    "managementIntensity": "Not recorded; all four scenarios are conditional comparators.",
                    "mlPredictionsEnabled": False},
    }
    return {**report, "gaezEvidence": snapshot}
