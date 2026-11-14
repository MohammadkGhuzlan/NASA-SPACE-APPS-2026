import math
from datetime import date
from .constants import PARAMETERS, START, END


def parse_date(text):
    result = date.fromisoformat(text)
    if not START <= result <= END:
        raise ValueError("Date outside 2019–2025 reference period")
    return result


def numeric(raw, parameter, fill=-999):
    if raw is None or str(raw).strip() in {"", "NA", "NaN", "null"}:
        return None, "missing"
    value = float(raw)
    if value in {fill, -999, -9999}:
        return None, "missing_fill"
    if not math.isfinite(value):
        raise ValueError(f"{parameter}: non-finite numeric value")
    _, lower, upper = PARAMETERS[parameter]
    if not lower <= value <= upper:
        raise ValueError(f"{parameter}: outside physical screening range [{lower}, {upper}]")
    return value, "valid"


def coords(lat, lon):
    lat, lon = float(lat), float(lon)
    if not math.isfinite(lat) or not math.isfinite(lon) or not -90 <= lat <= 90 or not -180 <= lon <= 180:
        raise ValueError("Invalid latitude/longitude")
    return lat, lon


def soil_values(row):
    result = {}
    ranges = {"clay_pct": (0, 100, "%"), "sand_pct": (0, 100, "%"), "silt_pct": (0, 100, "%"),
              "ph": (0, 14, "pH"), "soc_g_kg": (0, 1000, "g/kg")}
    for key, (lo, hi, unit) in ranges.items():
        raw = row[key]
        value = None if raw.strip() in {"", "-999", "-9999"} else float(raw)
        if value is not None and (not math.isfinite(value) or not lo <= value <= hi):
            raise ValueError(f"Invalid soil property {key}")
        result[key] = {"value": value, "unit": unit, "quality": "missing" if value is None else "proxy_not_farm_validated"}
    texture = [result[k]["value"] for k in ("clay_pct", "sand_pct", "silt_pct")]
    if all(v is not None for v in texture) and abs(sum(texture) - 100) > 1:
        raise ValueError("Clay + sand + silt must be within 1 percentage point of 100%")
    return result
