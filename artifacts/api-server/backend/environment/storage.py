from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from ..models import EnvironmentalValue, EnvironmentalLocation
from .constants import LOCATIONS, location_key


def ensure_location(db, lat, lon, study_id=None):
    key = location_key(lat, lon)
    cached = db.get(EnvironmentalLocation, key)
    if cached:
        return cached
    name = LOCATIONS[study_id][0] if study_id else f"{lat:.5f}, {lon:.5f}"
    db.execute(insert(EnvironmentalLocation).values(key=key, latitude=lat, longitude=lon,
        study_id=study_id, name=name, metadata_json={}).on_conflict_do_nothing())
    db.flush()
    return db.get(EnvironmentalLocation, key)


def store_values(db, records):
    """Immutable observations. Conflicts are reported, never updated in place."""
    if not records:
        return 0, 0, 0
    location = records[0]["location_key"]
    existing = {(v.date, v.parameter, v.product): (v.value, v.unit, v.classification) for v in
                db.scalars(select(EnvironmentalValue).where(EnvironmentalValue.location_key == location))}
    new, duplicates, conflicts = [], 0, 0
    for r in records:
        key = (r["date"], r["parameter"], r["product"])
        signature = (r["value"], r["unit"], r["classification"])
        if key in existing:
            if existing[key] == signature:
                duplicates += 1
            else:
                conflicts += 1
        else:
            new.append(r)
            existing[key] = signature
    inserted = 0
    for start in range(0, len(new), 500):
        statement = insert(EnvironmentalValue).values(new[start:start+500]).on_conflict_do_nothing().returning(EnvironmentalValue.id)
        inserted += len(db.execute(statement).all())
    return inserted, duplicates + len(new) - inserted, conflicts
