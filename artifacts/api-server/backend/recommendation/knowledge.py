"""Curated, attributed reference facts. None of these facts are training labels."""
from copy import deepcopy
from datetime import datetime, timezone
from sqlalchemy import select
from ..models import CropDefinition, CropRequirement, DataSource

VERSION = "agricultural-reference-2"
ECOCROP_DATASET = "https://github.com/OpenCLIM/ecocrop/blob/ea43ecd418fd1a1ea08d32c7dce64b7fae02dec4/EcoCrop_DB.csv"

REFERENCES = [
    {"id": "fao_ecocrop", "title": "FAO ECOCROP crop constraints and characteristics",
     "url": "https://gaez.fao.org/pages/ecocrop", "checkedOn": "2026-11-15",
     "scope": "The FAO database provides estimated crop environmental requirements. The selected records are from a CC BY 4.0 CGIAR Climate Action Data Hub export checked against FAO ECOCROP; values are expert estimates with uneven provenance, not measurements or validated local crop trials. Rainfall values are annual totals and must not be treated as crop-season rainfall."},
    {"id": "ecocrop_data_mirror", "title": "CGIAR Climate Action Data Hub: ECOCROP data, methods and quality notes",
     "url": "https://cgiar-climate-data-hub.github.io/catalog/ecocrop/",
     "checkedOn": "2026-11-15",
     "scope": "The export's documentation reports uneven expert-estimate provenance, missing thresholds for many species and known anomalous records retained as published. The app uses a small, pinned crop subset only."},
    {"id": "ecocrop_dataset", "title": "Pinned ECOCROP source export used for the app's crop subset",
     "url": ECOCROP_DATASET, "checkedOn": "2026-11-15",
     "scope": "OpenCLIM EcoCrop_DB.csv at commit ea43ecd418fd1a1ea08d32c7dce64b7fae02dec4. The matching CGIAR Climate Action Data Hub export is CC BY 4.0 and documents the FAO attribution and quality limits. This is a curated data export, not a replacement for local validation."},
    {"id": "nasa_power", "title": "NASA POWER daily meteorology and surface solar data",
     "url": "https://power.larc.nasa.gov/",
     "checkedOn": "2026-11-15",
     "scope": "Field Shift's existing exact-coordinate daily values for 2019–2025. Historical context only; NASA POWER is not a local crop calendar or field soil test."},
    {"id": "fao_water_manual", "title": "FAO Irrigation Water Management: Crop Water Needs, Chapter 3",
     "url": "https://www.fao.org/4/s2022e/s2022e07.htm", "checkedOn": "2026-11-15",
     "scope": "Tables 6 and 14: generic crop-cycle durations and indicative total crop-water ranges for the subset with values. These are not local cultivar calendars or irrigation prescriptions."},
    {"id": "fao_diversification", "title": "FAO Conservation Agriculture: Species diversification",
     "url": "https://www.fao.org/conservation-agriculture/in-practice/species-diversification/en/",
     "checkedOn": "2026-11-15",
     "scope": "General rotation and diversification principles. Potential effects depend on local crops, soils, pests and management; not quantified outcomes."},
    {"id": "fao_conservation", "title": "FAO Conservation Agriculture: Three principles",
     "url": "https://www.fao.org/conservation-agriculture/en", "checkedOn": "2026-11-15",
     "scope": "Minimum disturbance, permanent soil cover and species diversification; feasibility requires local assessment."},
    {"id": "usda_nrcs_rotation", "title": "USDA NRCS Conservation Crop Rotation (Practice Code 328)",
     "url": "https://www.nrcs.usda.gov/publications/nhcp-notice-179/328-cps-conservation-crop-rotation-2026.pdf",
     "checkedOn": "2026-11-15",
     "scope": "U.S. national conservation practice standard: plan crop sequence for stated goals and local conditions. Local/state Field Office Technical Guide and applicable standards are required; this is not a global prescription."},
    {"id": "usda_nrcs_cover", "title": "USDA NRCS Cover Crop (Practice Code 340)",
     "url": "https://www.nrcs.usda.gov/resources/guides-and-instructions/cover-crop-ac-340-conservation-practice-standard",
     "checkedOn": "2026-11-15",
     "scope": "National cover-crop practice overview notes erosion, soil organic matter and nutrient cycling purposes; state standards add local detail. Not a crop-specific or global management recommendation."},
]

LIMITATIONS = [
    "13 selected crop species only. Absence from this library does not mean a crop is unsuitable.",
    "ECOCROP values are expert estimates with uneven provenance; they are screening references, not field measurements or validated local trial results.",
    "ECOCROP annual-rainfall ranges are not directly compared with NASA rainfall or farm water budgets; crop-cycle interpretation varies by method.",
    "NASA monthly temperature context and ECOCROP broad thresholds flag possible conflicts only. They do not establish local suitability or planting dates.",
    "A SoilGrids value is a nearby soil proxy, not a farm soil test. Farmer-entered soil measurements remain self-reported even when marked laboratory confirmed.",
    "No trained model, suitability probability, yield prediction, economic ranking or guaranteed soil-health improvement.",
]

# ECOCROP values are transcribed from the attributed dataset version linked above.
# WaterMm is separately available only for crops with FAO manual values.
_ROWS = [
    ("wheat", "Wheat", "Triticum aestivum", 2114, "Gramineae", [15, 23], [5, 27], [750, 900], [300, 1600], [6, 7], [5.5, 8.5], [90, 250], [450, 650], ["bread wheat", "winter wheat", "spring wheat"]),
    ("barley", "Barley", "Hordeum vulgare", 1232, "Gramineae", [15, 20], [2, 40], [500, 1000], [200, 2000], [6.5, 7.5], [6, 8], [90, 240], [450, 650], []),
    ("maize", "Grain maize", "Zea mays ssp. mays", 238663, "Gramineae", [18, 33], [10, 47], [600, 1200], [400, 1800], [5, 7], [4.5, 8.5], [65, 365], [500, 800], ["corn", "maize", "grain corn"]),
    ("dry_bean", "Common bean", "Phaseolus vulgaris", 1668, "Leguminosae", [16, 25], [7, 32], [500, 2000], [300, 4300], [5.5, 7.5], [4, 9], [50, 270], [300, 500], ["dry bean", "dry beans", "common beans", "kidney bean"]),
    ("pea", "Pea", "Pisum sativum", 1721, "Leguminosae", [10, 24], [4, 30], [800, 1200], [350, 2500], [5.5, 7], [4.5, 8.3], [60, 140], [350, 500], ["peas", "field pea", "field peas"]),
    ("potato", "Potato", "Solanum tuberosum", 1971, "Solanaceae", [15, 25], [7, 30], [500, 800], [250, 2000], [5, 6.2], [4.2, 8.5], [90, 160], [500, 700], ["potatoes"]),
    ("sorghum", "Sorghum", "Sorghum bicolor", 48747, "Gramineae", [22, 35], [8, 40], [400, 600], [300, 700], [5.5, 7.5], [5, 8], [90, 300], None, ["grain sorghum"]),
    ("chickpea", "Chickpea", "Cicer arietinum", 2479, "Leguminosae", [15, 29], [7, 35], [600, 1000], [300, 1800], [6, 8.5], [4.7, 9.5], [90, 180], None, ["garbanzo", "gram"]),
    ("lentil", "Lentil", "Lens culinaris", 7209, "Leguminosae", [15, 29], [5, 32], [600, 1000], [250, 2500], [5.5, 7.5], [4.5, 8.2], [70, 240], None, ["lentils"]),
    ("oat", "Oat", "Avena sativa", 481, "Gramineae", [16, 20], [5, 30], [600, 1000], [250, 1500], [5, 6], [4.5, 7.5], [110, 270], None, ["oats"]),
    ("sunflower", "Sunflower", "Helianthus annuus", 1191, "Compositae", [17, 34], [5, 45], [600, 1000], [300, 1600], [6, 7.5], [5.5, 8], [70, 200], None, ["oilseed sunflower"]),
    ("soybean", "Soybean", "Glycine max", 1150, "Leguminosae", [20, 33], [10, 38], [600, 1500], [450, 1800], [5.5, 6.5], [4.5, 8.4], [75, 180], None, ["soya", "soyabean"]),
    ("rice", "Rice", "Oryza sativa", 1574, "Gramineae", [20, 30], [10, 36], [1500, 2000], [1000, 4000], [5.5, 7], [4.5, 9], [80, 180], None, ["paddy"]),
]


def _make_crop(row):
    (id, name, scientific, code, family, temp_opt, temp_limits,
     rain_opt, rain_limits, ph_opt, ph_limits, days, water, aliases) = row
    return {
        "id": id, "name": name, "group": family, "season": "not locally classified",
        "growingDays": days, **({"waterMm": water} if water else {}),
        "sourceIds": ["fao_ecocrop", "ecocrop_data_mirror", "ecocrop_dataset"] +
                     (["fao_water_manual"] if water else []),
        "limitations": [
            "ECOCROP's expert-estimated range is not a farm measurement or local suitability result.",
            "Temperature ranges and crop-cycle days do not validate a cultivar or local planting window.",
        ],
        "ecologicalRequirements": {
            "ecoPortCode": code, "scientificName": scientific, "botanicalFamily": family,
            "optimalTemperatureC": temp_opt, "broadTemperatureLimitsC": temp_limits,
            "optimalAnnualRainfallMm": rain_opt, "broadAnnualRainfallLimitsMm": rain_limits,
            "optimalSoilPh": ph_opt, "broadSoilPhLimits": ph_limits,
            "cropCycleDays": days,
            "sourceIds": ["fao_ecocrop", "ecocrop_data_mirror", "ecocrop_dataset"],
        },
        "aliases": aliases,
    }


CROPS = [_make_crop(row) for row in _ROWS]
BY_ID = {c["id"]: c for c in CROPS}
ALIASES = {a.casefold(): c["id"] for c in CROPS for a in [c["id"], c["name"], *c["aliases"]]}


def resolve(value):
    return ALIASES.get(value.strip().casefold())


def public_crop(c):
    return {k: deepcopy(v) for k, v in c.items() if k != "aliases"}


def library():
    return {"version": VERSION, "crops": [public_crop(c) for c in CROPS],
            "references": deepcopy(REFERENCES), "limitations": list(LIMITATIONS),
            "dataset": {"source": "FAO ECOCROP subset via CGIAR Climate Action Data Hub",
            "url": ECOCROP_DATASET, "license": "CC BY 4.0 (CGIAR Climate Action Data Hub export)",
                        "sourceSnapshotSha256": "4187e8846336e185c4583165211c5981855e95adfbefd897bd2bd481de48d106",
                        "attribution": "Source data from the FAO EcoCrop database, Food and Agriculture Organization of the United Nations."}}


def ensure_knowledge(db):
    """Idempotent data-only seeding into existing source and crop tables."""
    for ref in REFERENCES:
        row = db.get(DataSource, ref["id"])
        if row is None:
            row = DataSource(id=ref["id"], name=ref["title"], url=ref["url"],
                             status="reference_rules_only", description=ref["scope"])
            db.add(row)
        else:
            row.name, row.url, row.description = ref["title"], ref["url"], ref["scope"]
            row.status = "reference_rules_only"
    db.flush()
    for c in CROPS:
        row = db.scalar(select(CropDefinition).where(CropDefinition.name == c["name"]))
        if row is None:
            row = CropDefinition(name=c["name"], family=c["ecologicalRequirements"]["botanicalFamily"])
            db.add(row)
            db.flush()
        else:
            row.family = c["ecologicalRequirements"]["botanicalFamily"]
        for source_id in c["sourceIds"]:
            existing = db.scalars(select(CropRequirement).where(
                CropRequirement.crop_id == row.id, CropRequirement.source_id == source_id)).all()
            if not any(r.requirements.get("libraryVersion") == VERSION for r in existing):
                db.add(CropRequirement(crop_id=row.id, source_id=source_id,
                    requirements={**public_crop(c), "libraryVersion": VERSION,
                                  "classification": "REFERENCE_FACTS_NOT_TRAINING_LABELS"},
                    verified_at=datetime(2026, 11, 15, tzinfo=timezone.utc)))
    db.commit()
