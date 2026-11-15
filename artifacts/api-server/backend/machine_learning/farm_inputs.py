"""Server/research-only historical builder for the unchanged scientific contract.

No route accepts a root/path, payload, asserted provenance, or a feature vector.
An accepted model is still required before this data can produce predictions.
"""
from dataclasses import asdict
import math

from .contract import CONTRACT, CROPS, SCENARIO, PredictionInput, coordinates, validate_features
from .environment import acquire_power, acquire_soil


def label_cell(latitude, longitude):
    """Exact selected coordinate -> verified global five-arc-minute grid.

    Eastern/southern outer boundaries have no cell; do not wrap a farm into a
    different location. Interior boundaries use rasterio's top/left convention.
    """
    coordinates(latitude, longitude)
    if longitude == 180 or latitude == -90:
        raise ValueError("outside_source_extent")
    row = math.floor((90-latitude)*12)
    col = math.floor((longitude+180)*12)
    west, north = -180+col/12, 90-row/12
    return {"cell_id": f"RES05-SXX:{row}:{col}", "row": row, "col": col,
            "latitude": north-1/24, "longitude": west+1/24,
            "bounds_wgs84": [west, north-1/12, west+1/12, north]}


def prepare_location(latitude, longitude, crop, scenario, root, *, budget=None):
    """Bounded authentic acquisition; explicit refusals, no proxy substitutions.

    Run only after ownership/admission checks in any future live adapter.
    ``root`` is operator-controlled, never taken from an HTTP request.
    """
    result = {"status": "unavailable", "compatible": False, "model_request": None,
              "selected_coordinates": {"latitude": latitude, "longitude": longitude},
              "contract": CONTRACT, "crop": crop, "scenario": scenario, "reasons": []}
    if crop not in CROPS:
        return {**result, "status": "unsupported_input", "reasons": ["unsupported_crop"]}
    if scenario != SCENARIO:
        return {**result, "status": "unsupported_input", "reasons": ["unsupported_management_scenario"]}
    try:
        cell = label_cell(latitude, longitude)
    except (ValueError, TypeError) as exc:
        return {**result, "status": "unsupported_input", "reasons": [str(exc)]}
    result["label_cell"] = cell
    result["spatial_mapping"] = CONTRACT["spatial_rule"]
    result["provenance"] = {}
    try:
        if budget:
            budget.check()
        # Climate is intentionally prepared even if soil is unavailable, so an
        # operational check records genuine required-period climate separately.
        climate, power = acquire_power(cell["latitude"], cell["longitude"], root)
        result["provenance"]["climate"] = power
        result["climate_features"] = climate
        soil, soil_sources = acquire_soil(cell["latitude"], cell["longitude"], root)
        result["provenance"]["soil"] = soil_sources
        features = {**climate, **soil, "crop": crop, "scenario": scenario}
        validate_features(features)
        # Coverage geography must use the same label-cell center as training.
        # Keep the exact selected farm point above, separately from model
        # coordinates; otherwise points exactly on a block edge can be checked
        # against the neighboring block despite having this cell's features.
        request = PredictionInput(latitude=cell["latitude"], longitude=cell["longitude"],
                                  features=features)
        if budget:
            budget.check()
        result.update(status="prepared", compatible=True, model_request=asdict(request))
    except Exception as exc:
        # Preserve a refusal and the authentic partial provenance, not partial
        # model inputs or a zero-filled vector. No user-facing raw paths needed.
        result.update(reasons=["historical_inputs_unavailable", type(exc).__name__ + ":" + str(exc)])
    return result
