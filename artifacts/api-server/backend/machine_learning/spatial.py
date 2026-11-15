"""Deterministic geographic splits with conservative shared-footprint buffering."""
import hashlib
import math

import numpy as np
from pyproj import Geod

GEOD = Geod(ellps="WGS84")


def block(lat, lon):
    return f"{math.floor((lat+90)/10)}:{math.floor((lon+180)/10)}"


def region(lat, lon):
    """Geographic diagnostic strata, NOT verified climate-zone classes."""
    return f"lat{math.floor((lat+90)/30)}_lon{math.floor((lon+180)/60)}"


def partition(key, seed=42):
    value = int(hashlib.sha256(f"{seed}:{key}".encode()).hexdigest()[:8], 16) % 10
    return "test" if value < 2 else "validation" if value < 4 else "train"


def near(a, b, buffer_km=150):
    lon1, lat1 = a
    lon2, lat2 = b
    # Conservative union of possibly shared POWER footprints. A 1° latitude
    # or 1.25° longitude envelope exceeds the meteorological native grid.
    dlon = min(abs(lon1-lon2), 360-abs(lon1-lon2))
    footprint_overlap = abs(lat1-lat2) <= 1 and dlon <= 1.25
    return footprint_overlap or GEOD.inv(lon1, lat1, lon2, lat2)[2] < buffer_km*1000


def split(frame, seed=42, buffer_km=150):
    cells = frame.drop_duplicates("cell_id").sort_values("cell_id")
    assignment = {}
    kept = []
    # Test is untouched; validation near test is excluded; train near either excluded.
    for name in ("test", "validation", "train"):
        current = []
        for row in cells.itertuples():
            key = block(row.latitude, row.longitude)
            if partition(key, seed) != name:
                continue
            point = (row.longitude, row.latitude)
            if any(near(point, other, buffer_km) for other, other_name in kept if other_name != name):
                assignment[row.cell_id] = "buffer_excluded"
            else:
                assignment[row.cell_id] = name
                current.append((point, name))
        kept.extend(current)
    result = frame.copy()
    result["split"] = result.cell_id.map(assignment)
    result["block"] = [block(r.latitude, r.longitude) for r in result.itertuples()]
    result["region"] = [region(r.latitude, r.longitude) for r in result.itertuples()]
    return result


def assert_no_leakage(frame, buffer_km=150):
    cells = frame.drop_duplicates("cell_id")
    for key in ("cell_id", "block"):
        active = frame[frame.split != "buffer_excluded"]
        if (active.groupby(key).split.nunique() > 1).any():
            raise ValueError(f"Spatial leakage: {key}")
    rows = list(cells[cells.split != "buffer_excluded"].itertuples())
    for i, row in enumerate(rows):
        for other in rows[i+1:]:
            if row.split != other.split and near((row.longitude, row.latitude),
                                                 (other.longitude, other.latitude), buffer_km):
                raise ValueError("Shared coarse footprint or buffer leakage")
    return True


def buffered_cv(frame, folds, buffer_km=150):
    """Purge shared footprints/near neighbors inside training-only CV too."""
    for train_idx, validation_idx in folds:
        held = frame.iloc[validation_idx].drop_duplicates("cell_id")
        points = [(r.longitude, r.latitude) for r in held.itertuples()]
        safe = []
        for idx in train_idx:
            row = frame.iloc[idx]
            if not any(near((row.longitude, row.latitude), point, buffer_km) for point in points):
                safe.append(idx)
        if not safe:
            raise ValueError("No training geography remains after CV buffering")
        yield np.array(safe), validation_idx
