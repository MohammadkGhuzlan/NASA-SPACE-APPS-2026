"""Calendar-complete aggregates. Missing days are never silently interpolated."""
import calendar
from collections import defaultdict
from datetime import date, timedelta
from statistics import mean
from .constants import PARAMETERS, START, END, WARNINGS


def daily_rows(values):
    rows = {}
    for v in values:
        day = v.date.isoformat()
        rows.setdefault(day, {"date": day, **{p: None for p in PARAMETERS}})[v.parameter] = v.value
    return sorted(rows.values(), key=lambda r: r["date"])


def aggregate(rows, expected, hot_threshold=35):
    result = {"expectedDays": expected, "validDays": {}}
    for p in PARAMETERS:
        vals = [r[p] for r in rows if r.get(p) is not None]
        result["validDays"][p] = len(vals)
        result[p] = (sum(vals) if p == "PRECTOTCORR" else mean(vals)) if len(vals) == expected else None
    highs = [r["T2M_MAX"] for r in rows if r.get("T2M_MAX") is not None]
    for threshold, key in [(30, "hotDays30"), (35, "hotDays35"), (hot_threshold, "hotDays")]:
        result[key] = sum(v > threshold for v in highs) if len(highs) == expected else None
    result["maximumTemperature"] = max(highs) if len(highs) == expected else None
    lows = [r["T2M_MIN"] for r in rows if r.get("T2M_MIN") is not None]
    result["minimumTemperature"] = min(lows) if len(lows) == expected else None
    return result


def longest_dry_spell(rows, threshold):
    """Observed consecutive days below threshold; missing values/dates break runs."""
    best = run = 0
    previous = None
    for r in rows:
        current = date.fromisoformat(r["date"])
        if previous and current - previous != timedelta(days=1):
            run = 0
        rain = r.get("PRECTOTCORR")
        run = run + 1 if rain is not None and rain < threshold else 0
        best = max(best, run)
        previous = current
    return best


def summarize(rows, hot_threshold=35, dry_threshold=1):
    groups = defaultdict(list)
    annual_groups = defaultdict(list)
    season_groups = defaultdict(list)
    for r in rows:
        d = date.fromisoformat(r["date"])
        groups[d.strftime("%Y-%m")].append(r)
        annual_groups[d.year].append(r)
        season = "DJF" if d.month in (12, 1, 2) else "MAM" if d.month in (3, 4, 5) else "JJA" if d.month in (6, 7, 8) else "SON"
        # Calendar-year DJF (Jan/Feb/Dec); disclosed, not a cross-year winter.
        season_groups[(d.year, season)].append(r)
    monthly, annual, seasonal = [], [], []
    for year in range(2019, 2026):
        for month in range(1, 13):
            key = f"{year}-{month:02d}"
            monthly.append({"period": key, **aggregate(groups[key], calendar.monthrange(year, month)[1], hot_threshold)})
        n = 366 if calendar.isleap(year) else 365
        annual.append({"period": str(year), **aggregate(annual_groups[year], n, hot_threshold),
                       "longestDrySpell": longest_dry_spell(annual_groups[year], dry_threshold)
                           if any(r.get("PRECTOTCORR") is not None for r in annual_groups[year]) else None})
        for name, months in [("DJF", (1, 2, 12)), ("MAM", (3, 4, 5)), ("JJA", (6, 7, 8)), ("SON", (9, 10, 11))]:
            expected = sum(calendar.monthrange(year, m)[1] for m in months)
            seasonal.append({"period": f"{year}-{name}", **aggregate(season_groups[(year, name)], expected, hot_threshold)})
    # Anomalies: departure from same-calendar-month mean across COMPLETE years.
    for collection in (monthly, seasonal):
        for r in collection:
            peers = [x for x in collection if x["period"][5:] == r["period"][5:]]
            for p in ("PRECTOTCORR", "GWETTOP", "GWETROOT"):
                vals = [x[p] for x in peers if x[p] is not None]
                r[p + "ReferenceYears"] = len(vals)
                r[p + "Anomaly"] = r[p] - mean(vals) if r[p] is not None and vals else None
    for r in annual:
        vals = [x["PRECTOTCORR"] for x in annual if x["PRECTOTCORR"] is not None]
        r["PRECTOTCORRReferenceYears"] = len(vals)
        r["PRECTOTCORRAnomaly"] = r["PRECTOTCORR"] - mean(vals) if r["PRECTOTCORR"] is not None and vals else None
    return {"monthly": monthly, "annual": annual, "seasonal": seasonal,
            "hotThreshold": hot_threshold, "dryThreshold": dry_threshold,
            "referencePeriod": f"{START} to {END}", "warnings": list(WARNINGS),
            "drySpellDefinition": f"Longest observed consecutive run of daily precipitation < {dry_threshold} mm/day; gaps break runs. DJF uses Jan, Feb and Dec of the same calendar year."}
