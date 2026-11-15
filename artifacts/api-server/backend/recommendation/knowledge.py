"""Small, curated reference library. Facts are not GAEZ labels or local calendars."""
from copy import deepcopy
from datetime import datetime, timezone
from sqlalchemy import select
from ..models import CropDefinition, CropRequirement, DataSource

VERSION = "reference-library-1"
REFERENCES = [
    {"id": "fao_water_manual", "title": "FAO Irrigation Water Management: Crop Water Needs, Chapter 3",
     "url": "https://www.fao.org/4/s2022e/s2022e07.htm", "checkedOn": "2026-11-15",
     "scope": "Tables 6 and 14: indicative sowing-to-last-harvest durations and total crop water needs. Generic ranges, not local varieties, irrigation prescriptions or suitability thresholds."},
    {"id": "fao_diversification", "title": "FAO Conservation Agriculture: Species diversification",
     "url": "https://www.fao.org/conservation-agriculture/in-practice/species-diversification/en/", "checkedOn": "2026-11-15",
     "scope": "General rotation and diversification principles. Potential effects depend on local crops, soils, pests and management; not quantified outcomes."},
    {"id": "fao_conservation", "title": "FAO Conservation Agriculture: Three principles",
     "url": "https://www.fao.org/conservation-agriculture/en", "checkedOn": "2026-11-15",
     "scope": "Minimum disturbance, permanent soil cover and species diversification; feasibility requires local assessment."},
    {"id": "umn_rotation", "title": "University of Minnesota Extension: Small grain crop rotations",
     "url": "https://extension.umn.edu/small-grains-crop-and-variety-selection/small-grain-crop-rotations",
     "checkedOn": "2026-11-15",
     "scope": "Minnesota/North Dakota research, crop groups, warm/cool-season descriptors, small-grain repetition and corn-to-wheat disease cautions. Outside this region these are review prompts, not validated local prescriptions."},
]
LIMITATIONS = [
    "Six reference crops only. Absence from this library does not mean a crop is unsuitable.",
    "No verified global local planting calendars, crop-specific temperature/pH limits, cultivar, photoperiod or vernalization rules are loaded.",
    "FAO water ranges are indicative total crop evapotranspiration over a growing period, not irrigation depth. Rainfall is not effective rainfall.",
    "Extension crop-season descriptors and disease cautions have a Minnesota/North Dakota evidence scope, not worldwide validation.",
    "No trained model, suitability probability, yield prediction, economic ranking or guaranteed soil-health improvement.",
]


def crop(id, name, group, season, days, water, drought, aliases):
    return dict(id=id, name=name, group=group, season=season, growingDays=days,
                waterMm=water, droughtSensitivity=drought,
                sourceIds=["fao_water_manual", "umn_rotation"],
                limitations=["Generic FAO range; local cultivar and planting date can materially change duration and water use.",
                             "Soil pH, salinity, drainage and local adaptation remain unassessed."],
                aliases=aliases)


CROPS = [
    crop("wheat", "Wheat", "small_grain", "cool-season (regional descriptor)", [120, 150], [450, 650], "low-medium", ["durum wheat", "winter wheat", "spring wheat"]),
    crop("barley", "Barley", "small_grain", "cool-season (regional descriptor)", [120, 150], [450, 650], "low-medium", []),
    crop("maize", "Grain maize", "warm_grass", "warm-season (regional descriptor)", [125, 180], [500, 800], "medium-high", ["corn", "maize", "grain corn"]),
    crop("dry_bean", "Dry bean", "legume", "warm-season (regional descriptor)", [95, 110], [300, 500], "medium-high", ["dry beans", "bean", "beans", "common bean"]),
    crop("pea", "Pea", "legume", "cool-season (regional descriptor)", [90, 100], [350, 500], "medium-high", ["peas", "field pea", "field peas"]),
    crop("potato", "Potato", "tuber", "cool-season (regional descriptor)", [105, 145], [500, 700], "high", ["potatoes"]),
]
BY_ID = {c["id"]: c for c in CROPS}
ALIASES = {a.casefold(): c["id"] for c in CROPS for a in [c["id"], c["name"], *c["aliases"]]}


def resolve(value):
    return ALIASES.get(value.strip().casefold())


def public_crop(c):
    return {k: deepcopy(v) for k, v in c.items() if k != "aliases"}


def library():
    return {"version": VERSION, "crops": [public_crop(c) for c in CROPS],
            "references": deepcopy(REFERENCES), "limitations": list(LIMITATIONS)}


def ensure_knowledge(db):
    """Idempotent DML on existing tables; no schema changes or training labels."""
    for ref in REFERENCES:
        row = db.get(DataSource, ref["id"])
        if row is None:
            db.add(DataSource(id=ref["id"], name=ref["title"], url=ref["url"],
                              status="reference_rules_only", description=ref["scope"]))
    db.flush()
    for c in CROPS:
        row = db.scalar(select(CropDefinition).where(CropDefinition.name == c["name"]))
        if row is None:
            row = CropDefinition(name=c["name"], family=None)
            db.add(row)
            db.flush()
        existing = db.scalars(select(CropRequirement).where(
            CropRequirement.crop_id == row.id, CropRequirement.source_id == "fao_water_manual")).all()
        if not any(r.requirements.get("libraryVersion") == VERSION for r in existing):
            db.add(CropRequirement(crop_id=row.id, source_id="fao_water_manual",
                requirements={**public_crop(c), "libraryVersion": VERSION, "classification": "REFERENCE_FACTS_NOT_TRAINING_LABELS"},
                verified_at=datetime(2026, 11, 15, tzinfo=timezone.utc)))
    db.commit()
