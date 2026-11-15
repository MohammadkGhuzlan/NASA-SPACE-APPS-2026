"""Deterministic, source-linked scenario exploration, deliberately NOT suitability ML."""
from datetime import date, timedelta, datetime, timezone
from statistics import mean
from copy import deepcopy
from .knowledge import BY_ID, CROPS, REFERENCES, VERSION, LIMITATIONS, resolve, public_crop

ENGINE_VERSION = "reference-planner-1"


def finding(code, message, *sources):
    return {"code": code, "message": message, "sourceIds": list(sources)}


def calendar_for(crop, planted):
    if not planted:
        return {"status": "insufficient_evidence", "plantingDate": None,
                "harvestEarliest": None, "harvestLatest": None,
                "note": "Provide a hypothetical sowing date to calculate a duration-based harvest range. No local planting window has been verified.",
                "sourceIds": ["fao_water_manual"]}
    return {"status": "conditional_duration_estimate", "plantingDate": planted.isoformat(),
            "harvestEarliest": (planted + timedelta(days=crop["growingDays"][0])).isoformat(),
            "harvestLatest": (planted + timedelta(days=crop["growingDays"][1])).isoformat(),
            "note": "Farmer's hypothetical sowing date + generic FAO duration. Not a validated planting window or harvest forecast.",
            "sourceIds": ["fao_water_manual"]}


def seasonal_context(summary, planting, duration):
    if not planting:
        return {"status": "date_required", "note": "No crop-window climate comparison without a sowing assumption."}
    # Historical calendar-month context, not a crop-stage simulation or forecast.
    months = set()
    for n in range(duration):
        d = planting + timedelta(days=n)
        months.add(d.month)
    rows = [r for r in summary["monthly"] if int(r["period"][5:7]) in months]
    temps = [r["T2M"] for r in rows if r["T2M"] is not None]
    rains = [r["PRECTOTCORR"] for r in rows if r["PRECTOTCORR"] is not None]
    return {"status": "historical_month_context_only", "calendarMonths": sorted(months),
            "meanMonthlyTemperatureC": mean(temps) if temps else None,
            "meanMonthlyRainfallMm": mean(rains) if rains else None,
            "validTemperatureMonths": len(temps), "validRainfallMonths": len(rains),
            "referencePeriod": summary["referencePeriod"],
            "note": "2019–2025 averages across the calendar months touched by the maximum indicative growing period; equally weighted months, not crop-stage suitability or a forecast."}


def rotation_assessment(names):
    benefits, risks = [], []
    ids = [resolve(n) for n in names]
    known = [BY_ID[i] for i in ids if i]
    if any(i is None for i in ids):
        risks.append(finding("unknown_crop", "Some crops are outside the six-crop library; their requirements and transitions are unassessed."))
    for prev, nxt in zip(ids, ids[1:]):
        if not prev or not nxt:
            continue
        if prev == nxt:
            risks.append(finding("repeated_crop", f"{BY_ID[prev]['name']} follows itself; review crop-specific pest and disease carry-over.", "fao_diversification"))
        elif BY_ID[prev]["group"] == BY_ID[nxt]["group"]:
            risks.append(finding("same_group", f"{BY_ID[prev]['name']} → {BY_ID[nxt]['name']} repeats the same broad crop group; this is not a verified disease break.", "fao_diversification", "umn_rotation"))
        if prev == "maize" and nxt in {"wheat", "barley"}:
            risks.append(finding("maize_small_grain", "Corn residue before wheat/barley can maintain Fusarium inoculum in Minnesota/North Dakota evidence. Check local disease history and extension advice; this is not a global disease prediction.", "umn_rotation"))
    if len(set(i for i in ids if i)) >= 3:
        benefits.append(finding("diversification", "Three distinct reference crops introduce species diversity; benefits are conditional on local feasibility and management.", "fao_conservation", "fao_diversification"))
    if any(c["group"] == "legume" for c in known):
        benefits.append(finding("legume", "A legume introduces a possible biological nitrogen-fixation role. Effective nodulation, residues and local management must be checked; no fertilizer credit is calculated.", "fao_diversification", "umn_rotation"))
    risks.append(finding("local_validation", "Local adaptation, cultivar, pest history, herbicide carry-over, salinity, drainage, markets and equipment remain unverified.", "umn_rotation"))
    return benefits, risks


def scenario(slot, title, names, planted, history, budget):
    if not names:
        return {"slot": slot, "title": title, "crops": [], "status": "insufficient_evidence",
                "benefits": [], "risks": [finding("no_alternative", "No distinct, non-excluded reference sequence can be formed. Do not substitute unsupported crops.")],
                "waterRequirementMm": None, "schedule": []}
    benefits, risks = rotation_assessment([*history[-1:], *names])
    crops = [BY_ID.get(resolve(n)) for n in names]
    water = [sum(c["waterMm"][j] for c in crops) for j in (0, 1)] if all(crops) else None
    schedule = []
    earliest = latest = planted
    for n, c in zip(names, crops):
        if c is None:
            schedule.append({"crop": n, "status": "insufficient_evidence", "note": "No verified duration. Later dates are withheld."})
            earliest = latest = None
            continue
        cal = calendar_for(c, earliest)
        if latest and earliest:
            cal["plantingLatest"] = latest.isoformat()
            cal["harvestLatest"] = (latest + timedelta(days=c["growingDays"][1])).isoformat()
            earliest = earliest + timedelta(days=c["growingDays"][0])
            latest = latest + timedelta(days=c["growingDays"][1])
        cal.update(crop=c["name"], note=cal["note"] + " Later crops assume immediate succession with no turnaround; actual local seasonal gaps may be required.")
        schedule.append(cal)
    if budget is not None:
        risks.append(finding("water_budget_scope", "The water budget is for one crop season, whereas sequence water totals span multiple crop cycles. No sequence-wide budget adequacy is inferred.", "fao_water_manual"))
        for c in crops:
            if c and budget < c["waterMm"][0]:
                risks.append(finding("crop_water_budget_conflict", f"{c['name']}: farmer-estimated water is below the generic single-crop minimum. Resolve this before considering this sequence.", "fao_water_manual"))
    return {"slot": slot, "title": title, "crops": names, "status": "conditional_scenario",
            "benefits": benefits, "risks": risks, "waterRequirementMm": water, "schedule": schedule}


def build_report(farm, inputs, summary, features, drafts):
    profile = farm.profile
    excluded = {resolve(n) for n in inputs.excludedCrops}
    budget = inputs.availableSeasonalWaterMm
    current = inputs.currentRotation or [profile["currentCrop"]]
    history = inputs.previousCrops
    candidates = []
    for c in CROPS:
        if c["id"] in excluded:
            continue
        risks = [finding("not_suitability", "This is a reference crop to investigate, not a finding that this crop is locally suitable.", "fao_water_manual")]
        reasons = [finding("reference_available", "Indicative duration and total crop-water ranges are traceable to FAO tables.", "fao_water_manual")]
        status = "conditional_candidate"
        if budget is not None and budget < c["waterMm"][0]:
            status = "water_budget_conflict"
            risks.append(finding("water_budget_conflict", f"Farmer-estimated crop-available water ({budget:g} mm) is below the generic range minimum ({c['waterMm'][0]} mm). Range is not an irrigation prescription.", "fao_water_manual"))
        elif budget is not None:
            risks.append(finding("water_unvalidated", "Budget does not prove adequacy: timing, effective rainfall, soil storage and local evapotranspiration remain unknown.", "fao_water_manual"))
        if profile["irrigation"] == "rainfed":
            risks.append(finding("rainfed", "Rainfed system: historical rain is context only, not effective rainfall or proof of water adequacy.", "fao_water_manual"))
        if profile.get("waterConstraints") or profile.get("agriculturalConstraints") or inputs.operationalLimitations:
            risks.append(finding("constraints_review", "Farmer-described constraints are retained below but are not automatically interpreted. Resolve them before acting."))
        candidates.append({"crop": public_crop(c), "status": status, "reasons": reasons, "risks": risks,
                           "calendar": calendar_for(c, inputs.plantingDate),
                           "environmentalContext": seasonal_context(summary, inputs.plantingDate, c["growingDays"][1])})
    eligible = [BY_ID[r["crop"]["id"]] for r in candidates if r["status"] != "water_budget_conflict"]
    # Transparent exploration ordering, not a statistical or agronomic score.
    if profile["goal"] == "conserve_water":
        eligible.sort(key=lambda c: (c["waterMm"][0], c["id"]))
    elif profile["goal"] == "soil_health":
        eligible.sort(key=lambda c: (c["group"] != "legume", c["id"]))
    else:
        eligible.sort(key=lambda c: c["id"])
    sequences = []
    from itertools import permutations
    for seq in permutations(eligible, 3):
        ids = [c["id"] for c in seq]
        prior = resolve(current[-1]) if current else None
        transitions = ([prior] if prior else []) + ids
        if any(a == b or (a and BY_ID[a]["group"] == BY_ID[b]["group"]) or
               (a == "maize" and b in {"wheat", "barley"})
               for a, b in zip(transitions, transitions[1:])):
            continue
        if not any(c["group"] == "legume" for c in seq):
            continue
        sequences.append([c["name"] for c in seq])
        if len(sequences) == 2:
            break
    scenarios = [scenario("current", "Current rotation (farmer reported)", current, inputs.plantingDate, history, budget)]
    for i, label in enumerate(("A", "B")):
        seq = sequences[i] if len(sequences) > i else []
        scenarios.append(scenario("alternative_" + label.lower(), "Alternative " + label + " — conditional exploration",
                                  seq, inputs.plantingDate, [*history, *current], budget))
    missing = ["Verified local planting/harvesting calendar and cultivar selection",
               "Crop-specific soil limits, drainage, salinity, pests and market/equipment feasibility",
               "Validated suitability labels and trained model (later phase)"]
    if not inputs.plantingDate:
        missing.append("A farmer-chosen hypothetical sowing date")
    if not history and profile.get("cropHistory"):
        missing.append("Structured previous crops: free-text profile history was retained but not silently parsed")
    elif not history:
        missing.append("Previous crops and their chronological order")
    if budget is None:
        missing.append("Quantified crop-available seasonal water; irrigation category alone does not establish supply")
    if not summary["availableParameters"]:
        missing.append("Environmental observations for the exact selected coordinates")
    missing += [f"Matching source-aware 0–5 cm soil input: {k}" for k, v in features["soilInputs"].items() if v["value"] is None]
    if any(v["source"] == "PROXY_DEMO_ONLY" for v in features["soilInputs"].values()):
        missing.append("Farm-validated soil tests: nearby SoilGrids proxy inputs are not farm measurements")
    management = [
        finding("soil_cover", "Discuss retaining residues or locally appropriate cover crops to reduce exposed soil. Check livestock use, pests, water competition and equipment before adopting.", "fao_conservation"),
        finding("disturbance", "Consider locally feasible reduced-disturbance practices; do not change tillage without reviewing weeds, soil condition and equipment.", "fao_conservation"),
        finding("water_management", "Use local evapotranspiration, effective rainfall, soil storage and irrigation efficiency for a water plan. This report does not prescribe irrigation depth or frequency.", "fao_water_manual"),
        finding("diversity", "Review species diversity and legume integration with local extension; benefits and disease breaks are not guaranteed.", "fao_diversification"),
    ]
    return {"farmId": farm.id, "createdAt": datetime.now(timezone.utc).isoformat(),
            "knowledgeVersion": VERSION, "engineVersion": ENGINE_VERSION,
            "status": "reference_based_plan" if sequences and summary["availableParameters"] else "insufficient_evidence",
            "modelStatus": "not_trained",
            "inputs": {"planning": inputs.model_dump(mode="json"), "farmerProfile": deepcopy(profile),
                       "sources": {"farmerProfile": "farmer_reported_unverified", "planning": "farmer_reported_scenario_assumptions"},
                       "savedManualDrafts": [{"slot": d.slot, "name": d.name, "crops": d.crops, "notes": d.notes} for d in drafts]},
            "candidates": candidates, "scenarios": scenarios, "management": management,
            "missingInformation": missing,
            "warnings": [*LIMITATIONS, "Alternatives are deterministic reference-based exploration, not ranked suitability. Water-priority ordering uses generic FAO minimum water range; soil-health ordering brings a legume first. No quantified benefit is implied.",
                         "Operational constraints and free-text history require human review; no language model interprets them.",
                         *summary["warnings"]],
            "references": deepcopy(REFERENCES),
            "environmentalEvidence": {"location": summary["location"], "status": summary["status"],
                "referencePeriod": summary["referencePeriod"], "parameters": summary["availableParameters"],
                "provenance": summary["provenance"], "soilInputs": features["soilInputs"],
                "annual": summary["annual"], "irrigation": features["irrigation"],
                "note": "Exact selected-coordinate NASA context. Proxy soil values are not tests, training labels or suitability proof."}}
