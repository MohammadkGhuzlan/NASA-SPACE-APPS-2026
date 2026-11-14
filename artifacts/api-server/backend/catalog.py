"""Reference metadata only: never seed measurements or recommendations."""
from sqlalchemy.dialects.postgresql import insert
from .models import DataSource

SOURCES = [
    {"id": "nasa_power", "name": "NASA POWER", "url": "https://power.larc.nasa.gov/", "status": "connected_on_demand", "description": "Daily T2M (°C), T2M_MAX (°C), PRECTOTCORR (mm/day), aggregated for 2025. Gridded estimates, not field measurements. Missing days remain gaps."},
    {"id": "openstreetmap", "name": "OpenStreetMap / Nominatim", "url": "https://www.openstreetmap.org/copyright", "status": "connected", "description": "Global basemap and place search. © OpenStreetMap contributors. Not an environmental observation source."},
    {"id": "farmer", "name": "Farmer-provided information", "url": "", "status": "user_provided", "description": "Unverified user entries. Soil moisture is volumetric water content (%), area is hectares, pH is dimensionless."},
    {"id": "nasa_smap", "name": "NASA SMAP soil moisture", "url": "https://smap.jpl.nasa.gov/", "status": "not_connected", "description": "Planned soil moisture integration. No SMAP measurements are displayed."},
    {"id": "nasa_modis", "name": "NASA MODIS vegetation", "url": "https://modis.gsfc.nasa.gov/", "status": "not_connected", "description": "Planned vegetation integration. No vegetation index or crop-health score is inferred."},
    {"id": "crop_requirements", "name": "Verified crop requirements", "url": "https://www.fao.org/land-water/databases-and-software/crop-information/en/", "status": "not_imported", "description": "Future curation reference, not an imported dataset. No crop suitability, rules-based recommendations or trained model is operational."},
]


def ensure_source_registry(db):
    for source in SOURCES:
        db.execute(insert(DataSource).values(**source).on_conflict_do_nothing(index_elements=["id"]))
    db.commit()
