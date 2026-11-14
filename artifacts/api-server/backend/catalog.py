"""Reference metadata only: never seed measurements or recommendations."""
from sqlalchemy.dialects.postgresql import insert
from .models import DataSource

SOURCES = [
    {"id": "nasa_power", "name": "NASA POWER climate", "url": "https://power.larc.nasa.gov/", "status": "imported_and_on_demand", "description": "2019–2025 daily T2M/T2M_MAX/T2M_MIN (C), PRECTOTCORR (mm/day) and RH2M (%). Gridded estimates, not field sensors. Uploaded climate units are mapped from NASA definitions; original retrieval date/time standard were absent."},
    {"id": "nasa_power_wetness", "name": "NASA POWER modeled wetness (not SMAP)", "url": "https://power.larc.nasa.gov/", "status": "imported_and_on_demand", "description": "2019–2025 GWETTOP and GWETROOT, dimensionless 0–1 wetness fractions. Upper 5 cm / generally upper 1 m. Not volumetric moisture, irrigation demand or crop damage."},
    {"id": "soilgrids", "name": "ISRIC SoilGrids nearby proxies", "url": "https://soilgrids.org/", "status": "proxy_demo_only", "description": "Four 0–5 cm nearby modeled soil estimates, PROXY_DEMO_ONLY. Not farm tests or ground-truth labels. Original and sampled positions and distances are retained; Al Ain distance discrepancy is flagged."},
    {"id": "openstreetmap", "name": "OpenStreetMap / Nominatim", "url": "https://www.openstreetmap.org/copyright", "status": "connected", "description": "Global basemap and place search. © OpenStreetMap contributors. Not an environmental observation source."},
    {"id": "farmer", "name": "Farmer-provided information", "url": "", "status": "user_provided", "description": "Unverified user entries. Soil moisture is volumetric water content (%), area is hectares, pH is dimensionless."},
    {"id": "nasa_smap", "name": "NASA SMAP soil moisture", "url": "https://smap.jpl.nasa.gov/", "status": "not_connected", "description": "Planned soil moisture integration. No SMAP measurements are displayed."},
    {"id": "nasa_modis", "name": "NASA MODIS vegetation", "url": "https://modis.gsfc.nasa.gov/", "status": "not_connected", "description": "Planned vegetation integration. No vegetation index or crop-health score is inferred."},
    {"id": "crop_requirements", "name": "Verified crop requirements", "url": "https://www.fao.org/land-water/databases-and-software/crop-information/en/", "status": "not_imported", "description": "Future curation reference, not an imported dataset. No crop suitability, rules-based recommendations or trained model is operational."},
]


def ensure_source_registry(db):
    for source in SOURCES:
        db.execute(insert(DataSource).values(**source).on_conflict_do_update(index_elements=["id"],
            set_={k: v for k, v in source.items() if k != "id"}))
    db.commit()
