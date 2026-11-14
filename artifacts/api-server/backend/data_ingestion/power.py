"""NASA POWER retrieval. No synthetic or interpolated measurements."""
import calendar
import logging
from datetime import datetime, timezone
import httpx

logger = logging.getLogger(__name__)
YEAR = 2025
POWER_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"


def unavailable(reason):
    return {
        "status": "unavailable", "source": "NASA POWER",
        "sourceUrl": "https://power.larc.nasa.gov/",
        "dateRange": f"{YEAR}-01-01 to {YEAR}-12-31",
        "monthly": [], "heatDays": None, "soilMoisture": None,
        "vegetationIndex": None, "fetchedAt": None,
        "warnings": [reason, "No soil or vegetation satellite products are connected. No suitability assessment has been performed."],
    }


def fetch_environment(latitude, longitude):
    params = {
        "parameters": "T2M,T2M_MAX,PRECTOTCORR", "community": "AG",
        "latitude": latitude, "longitude": longitude,
        "start": f"{YEAR}0101", "end": f"{YEAR}1231", "format": "JSON",
    }
    try:
        with httpx.Client(timeout=25) as client:
            response = client.get(POWER_URL, params=params)
            response.raise_for_status()
            values = response.json()["properties"]["parameter"]
        temps = values["T2M"]
        rain = values["PRECTOTCORR"]
        highs = values["T2M_MAX"]
        def valid(x):
            return isinstance(x, (int, float)) and x > -900
        monthly = []
        missing = False
        for month in range(1, 13):
            prefix = f"{YEAR}{month:02d}"
            n_days = calendar.monthrange(YEAR, month)[1]
            t = [v for k, v in temps.items() if k.startswith(prefix) and valid(v)]
            r = [v for k, v in rain.items() if k.startswith(prefix) and valid(v)]
            # Do not imply complete monthly totals when days are missing.
            complete_t, complete_r = len(t) == n_days, len(r) == n_days
            missing |= not complete_t or not complete_r
            monthly.append({
                "month": calendar.month_abbr[month],
                "temperature": round(sum(t) / len(t), 2) if complete_t else None,
                "rainfall": round(sum(r), 2) if complete_r else None,
            })
        if not any(m["temperature"] is not None or m["rainfall"] is not None for m in monthly):
            return unavailable("NASA POWER returned no complete months for this location.")
        h = [v for v in highs.values() if valid(v)]
        warnings = [
            "NASA POWER is gridded environmental data, not an on-farm sensor. Its spatial resolution may not represent field microclimates.",
            "Soil moisture and vegetation satellite products are not connected. Crop suitability, soil-health impact and risk are not assessed.",
            "Heat exposure is days with daily maximum air temperature ≥35°C; this is a descriptive threshold, not a crop-specific risk score.",
        ]
        if missing:
            warnings.append("Incomplete months are shown as gaps, not estimated or zero-filled.")
        return {
            "status": "partial" if missing else "available", "source": "NASA POWER",
            "sourceUrl": str(response.url), "dateRange": f"{YEAR}-01-01 to {YEAR}-12-31",
            "monthly": monthly, "heatDays": sum(v >= 35 for v in h) if len(h) == 365 else None,
            "soilMoisture": None, "vegetationIndex": None,
            "fetchedAt": datetime.now(timezone.utc).isoformat(), "warnings": warnings,
        }
    except (httpx.HTTPError, KeyError, ValueError, TypeError):
        logger.warning("NASA POWER retrieval unavailable")
        return unavailable("NASA POWER could not be retrieved. Retry later; no substitute measurements are displayed.")
