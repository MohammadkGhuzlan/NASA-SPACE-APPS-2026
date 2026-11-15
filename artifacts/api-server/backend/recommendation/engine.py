"""Source-linked rule-based planning. This module never trains or predicts."""
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from itertools import permutations
from statistics import mean
from .knowledge import BY_ID, CROPS, REFERENCES, VERSION, LIMITATIONS, resolve, public_crop

ENGINE_VERSION = "reference-planner-2"


def finding(code, message, *sources):
    return {"code": code, "message": message, "sourceIds": list(sources)}


def calendar_for(crop, planted):
    days = crop["growingDays"]
    if not planted:
        return {"status": "date_required", "plantingDate": None, "cycleDays": days,
                "harvestEarliest": None, "harvestLatest": None,
                "note": "Provide a hypothetical sowing date. The cycle range is an ECOCROP expert estimate, not a local calendar or harvest forecast.",
                "sourceIds": crop["ecologicalRequirements"]["sourceIds"]}
    return {"status": "conditional_duration_estimate", "plantingDate": planted.isoformat(),
            "cycleDays": days,
            "harvestEarliest": (planted + timedelta(days=days[0])).isoformat(),
            "harvestLatest": (planted + timedelta(days=days[1])).isoformat(),
            "note": "Farmer's hypothetical sowing date plus the broad ECOCROP crop-cycle range; not a validated planting window or harvest forecast.",
            "sourceIds": crop["ecologicalRequirements"]["sourceIds"]}


def _window_months(planting, days):
    if not planting:
        return []
    return sorted({(planting + timedelta(days=n)).month for n in range(max(1, days))})


def seasonal_context(summary, planting, crop):
    if not planting:
        return {"status": "date_required", "note": "Provide a hypothetical sowing date for NASA calendar-month context."}
    months = _window_months(planting, crop["growingDays"][1])
    rows = [r for r in summary.get("monthly", []) if int(r["period"][5:7]) in months]
    def complete(parameter):
        return [r[parameter] for r in rows if r.get(parameter) is not None and
                r.get("validDays", {}).get(parameter) == r.get("expectedDays")]
    temps, lows, highs, rains, top_wetness, root_wetness = (
        complete(p) for p in ("T2M", "T2M_MIN", "T2M_MAX", "PRECTOTCORR", "GWETTOP", "GWETROOT"))
    eco = crop["ecologicalRequirements"]
    min_limit, max_limit = eco["broadTemperatureLimitsC"]
    observed_low = min(lows) if lows else None
    observed_high = max(highs) if highs else None
    # These are comparisons of 2019–2025 monthly means of daily extrema,
    # not counts of daily threshold events or a crop-stage model.
    cold = observed_low is not None and observed_low < min_limit
    heat = observed_high is not None and observed_high > max_limit
    return {"status": "historical_month_context_only", "calendarMonths": months,
            "monthlyMeanTemperatureC": mean(temps) if temps else None,
            "monthlyMeanDailyMinimumC": observed_low,
            "monthlyMeanDailyMaximumC": observed_high,
            "meanMonthlyRainfallMm": mean(rains) if rains else None,
            "meanMonthlyNASA_GWETTOP": mean(top_wetness) if top_wetness else None,
            "meanMonthlyNASA_GWETROOT": mean(root_wetness) if root_wetness else None,
            "validTemperatureMonths": len(temps), "validRainfallMonths": len(rains),
            "validGWETTOPMonths": len(top_wetness), "validGWETROOTMonths": len(root_wetness),
            "referencePeriod": summary.get("referencePeriod"),
            "ecocropBroadTemperatureLimitsC": eco["broadTemperatureLimitsC"],
            "potentialColdThresholdMismatch": cold,
            "potentialHeatThresholdMismatch": heat,
            "note": "NASA POWER 2019–2025 monthly means across all months touched by the maximum ECOCROP cycle. Monthly mean daily extrema are compared with expert-estimated broad thresholds as a review flag only; rainfall and modeled GWETTOP/GWETROOT are context, not effective rainfall, field moisture, daily threshold counts, crop-stage response or forecast.",
            "sourceIds": ["nasa_power", "fao_ecocrop", "ecocrop_data_mirror"]}


def _soil_screen(crop, soil_inputs):
    ph = soil_inputs.get("ph", {})
    value = ph.get("value")
    source = ph.get("source", "unavailable")
    eco = crop["ecologicalRequirements"]
    if value is None:
        return "missing", None
    lo, hi = eco["broadSoilPhLimits"]
    opt_lo, opt_hi = eco["optimalSoilPh"]
    is_proxy = source == "PROXY_DEMO_ONLY"
    in_broad = lo <= value <= hi
    in_optimal = opt_lo <= value <= opt_hi
    return ("proxy_only" if is_proxy else "farmer_reported"), {
        "value": value, "source": source, "depthCm": ph.get("depthCm", "0-5"),
        "ecoCropBroadRange": [lo, hi], "ecoCropOptimalRange": [opt_lo, opt_hi],
        "withinBroadRange": in_broad, "withinOptimalRange": in_optimal,
        "note": ("Nearby SoilGrids proxy is context only and never filters this crop."
                 if is_proxy else
                 "Farmer-entered result is self-reported, not independently verified; a 0–5 cm sample may not represent the full crop root zone."),
    }


def _candidate_evidence(crop, summary, features, inputs, planted):
    reasons = [finding(
        "ecocrop_reference", "FAO ECOCROP ecological ranges are available for this species; they are expert estimates, not local validation.",
        "fao_ecocrop", "ecocrop_data_mirror")]
    risks = []
    context = seasonal_context(summary, planted, crop)
    climate = context.get("potentialColdThresholdMismatch") or context.get("potentialHeatThresholdMismatch")
    if context.get("potentialColdThresholdMismatch"):
        risks.append(finding("possible_cold_threshold_mismatch",
            "The historical monthly mean daily minimum during the assumed crop window is below the broad ECOCROP threshold. Review locally; this is not a crop-failure prediction.",
            "fao_ecocrop", "ecocrop_data_mirror"))
    if context.get("potentialHeatThresholdMismatch"):
        risks.append(finding("possible_heat_threshold_mismatch",
            "The historical monthly mean daily maximum during the assumed crop window is above the broad ECOCROP threshold. Review locally; this is not a crop-failure prediction.",
            "fao_ecocrop", "ecocrop_data_mirror"))

    soil_status, soil = _soil_screen(crop, features.get("soilInputs", {}))
    soil_conflict = bool(soil and not soil["withinBroadRange"] and soil_status == "farmer_reported")
    if soil_status == "missing":
        risks.append(finding("soil_ph_missing", "No matching 0–5 cm pH input is available for comparison; crop soil response is not assessed.",
                             "fao_ecocrop"))
    elif soil_status == "proxy_only":
        risks.append(finding("soil_proxy_not_filter", "A nearby SoilGrids proxy is shown for context only; it is not farm soil and does not screen out this crop.",
                             "fao_ecocrop", "ecocrop_data_mirror"))
    elif soil_conflict:
        risks.append(finding("possible_soil_ph_mismatch", "The farmer-reported 0–5 cm pH is outside ECOCROP's broad estimate range. Verify the sample, depth and local crop guidance before considering this crop.",
                             "fao_ecocrop", "ecocrop_data_mirror"))
    elif soil and not soil["withinOptimalRange"]:
        risks.append(finding("soil_ph_outside_optimal", "The farmer-reported pH is inside ECOCROP's broad range but outside its narrower optimal estimate; this is a review point, not a rejection.",
                             "fao_ecocrop", "ecocrop_data_mirror"))
    else:
        reasons.append(finding("soil_ph_within_reference", "The supplied pH falls within ECOCROP's broad estimate range. This does not establish farm suitability.",
                               "fao_ecocrop", "ecocrop_data_mirror"))

    water_conflict = False
    demand = crop.get("waterMm")
    if inputs.availableSeasonalWaterMm is not None and demand:
        lower, upper = demand
        water_conflict = inputs.availableSeasonalWaterMm < lower
        if water_conflict:
            risks.append(finding("potential_water_shortfall", f"Farmer-estimated crop-available seasonal water ({inputs.availableSeasonalWaterMm:g} mm) is below the generic FAO crop-water range ({lower}–{upper} mm). This is a review flag, not an irrigation prescription.",
                                 "fao_water_manual"))
        else:
            risks.append(finding("water_budget_not_proof", "The farmer's seasonal water estimate overlaps the generic FAO crop-water range, but timing, soil storage, effective rainfall and irrigation delivery are not verified.",
                                 "fao_water_manual"))
    elif inputs.availableSeasonalWaterMm is not None:
        risks.append(finding("crop_water_need_unavailable", "No comparable FAO crop-water range is loaded for this species; the entered water quantity cannot screen it.",
                             "fao_ecocrop"))
    if features.get("irrigation") == "rainfed":
        risks.append(finding("rainfed_system", "Farm profile says rainfed. NASA rainfall and wetness context do not establish effective crop water or adequacy.",
                             "fao_water_manual"))
    elif features.get("irrigation") in {"limited", "fully_irrigated"}:
        risks.append(finding("irrigation_capacity_unverified", "The irrigation category is farmer-reported; seasonal delivery capacity, timing, water quality and reliability are not measured.",
                             "usda_nrcs_rotation"))

    # Unknown or flagged evidence is ordered later, not converted into a score.
    flagged = climate or soil_conflict or water_conflict
    review = {"climate": context, "soilPH": soil, "soilStatus": soil_status,
              "waterConflict": water_conflict}
    return reasons, risks, review, flagged


def rotation_assessment(names):
    benefits, risks = [], []
    ids = [resolve(n) for n in names]
    known = [BY_ID[i] for i in ids if i]
    if any(i is None for i in ids):
        risks.append(finding("unknown_crop", "Some crops are outside the 13-species library; their environmental requirements and family transitions are unassessed."))
    for prev, nxt in zip(ids, ids[1:]):
        if not prev or not nxt:
            continue
        prev_crop, next_crop = BY_ID[prev], BY_ID[nxt]
        if prev == nxt:
            risks.append(finding("repeated_crop", f"{next_crop['name']} follows itself; review crop-specific pest and disease history with local extension.",
                                 "usda_nrcs_rotation"))
        elif prev_crop["group"] == next_crop["group"]:
            risks.append(finding("same_botanical_family", f"{prev_crop['name']} → {next_crop['name']} repeats botanical family {next_crop['group']}; this is not evidence of a local disease break.",
                                 "usda_nrcs_rotation", "fao_diversification"))
    families = {c["group"] for c in known}
    if len(families) >= 2:
        benefits.append(finding("family_diversity", "The sequence contains multiple botanical families. NRCS describes crop diversity as a planning consideration; local objectives and feasible crops still determine the design.",
                                "usda_nrcs_rotation", "fao_diversification"))
    if any(c["group"] == "Leguminosae" for c in known):
        benefits.append(finding("legume_role", "A legume is included. Nitrogen contribution depends on species, nodulation, biomass, residue handling and local management; no fertilizer credit is estimated.",
                                "usda_nrcs_rotation"))
    risks.append(finding("local_rotation_review", "Pest life cycles, family-specific break intervals, herbicide carry-over, cultivar, soil constraints, markets and equipment need local extension review.",
                         "usda_nrcs_rotation"))
    return benefits, risks


def _scenario(slot, title, names, schedule_names, planted, history, budget, strategy_type="conditional_rule_sequence"):
    if not names:
        return {"slot": slot, "title": title, "strategyType": strategy_type, "crops": [],
                "status": "insufficient_evidence", "benefits": [],
                "risks": [finding("no_supported_sequence", "Not enough non-excluded reference crops remain to form a distinct multi-crop alternative. No unsupported crop was substituted.")],
                "waterRequirementMm": None, "schedule": []}
    benefits, risks = rotation_assessment(names)
    crops = [BY_ID.get(resolve(n)) for n in names]
    water = [sum(c["waterMm"][j] for c in crops) for j in (0, 1)] if all(c and c.get("waterMm") for c in crops) else None
    schedule = []
    earliest = latest = planted
    for n in schedule_names:
        c = BY_ID.get(resolve(n))
        if c is None:
            schedule.append({"crop": n, "status": "insufficient_evidence", "note": "No ECOCROP cycle estimate for this entry; later dates are withheld."})
            earliest = latest = None
            continue
        cal = calendar_for(c, earliest)
        if latest and earliest:
            cal["plantingLatest"] = latest.isoformat()
            cal["harvestLatest"] = (latest + timedelta(days=c["growingDays"][1])).isoformat()
            earliest += timedelta(days=c["growingDays"][0])
            latest += timedelta(days=c["growingDays"][1])
        cal.update(crop=c["name"],
                   note=cal["note"] + " Later crops assume immediate succession without turnaround; actual local seasonal gaps may be required.")
        schedule.append(cal)
    if budget is not None and len(names) > 1:
        risks.append(finding("water_budget_scope", "The entered budget applies to one crop season, while a rotation sequence spans successive crop cycles. No sequence-wide adequacy is inferred.",
                             "fao_water_manual"))
        for c in crops:
            if c and c.get("waterMm") and budget < c["waterMm"][0]:
                risks.append(finding("crop_water_budget_conflict", f"{c['name']}: the entered single-season water estimate is below the generic FAO range minimum. Resolve before considering this sequence.",
                                     "fao_water_manual"))
    return {"slot": slot, "title": title, "strategyType": strategy_type, "crops": names,
            "status": "conditional_scenario", "benefits": benefits, "risks": risks,
            "waterRequirementMm": water, "schedule": schedule}


def _alternative_sequences(candidates, priority, previous, current):
    # Distinct crop families are preferred; this is a transparent tie-break rule,
    # not an agronomic or statistical score.
    known = list(candidates)
    if len(known) < 2:
        return []
    length = min(3, len(known))
    options = []
    previous_id = resolve((previous + current)[-1]) if previous or current else None
    for seq in permutations(known, length):
        crops = [BY_ID[x["crop"]["id"]] for x in seq]
        transitions = ([BY_ID[previous_id]] if previous_id else []) + crops
        if any(a["group"] == b["group"] for a, b in zip(transitions, transitions[1:])):
            continue
        if len({c["group"] for c in crops}) < min(2, length):
            continue
        ids = tuple(c["id"] for c in crops)
        if priority == "conserve_water":
            # A sequence with unknown comparative requirements is never
            # described or treated as water efficient.
            water_key = (not all(c.get("waterMm") for c in crops),
                         sum(c["waterMm"][0] for c in crops) if all(c.get("waterMm") for c in crops) else float("inf"))
        elif priority in {"soil_health", "reduce_risk"}:
            water_key = ()
        else:
            water_key = ()
        family_count = len({c["group"] for c in crops})
        if priority == "soil_health":
            family_key = (not any(c["group"] == "Leguminosae" for c in crops), -family_count)
        elif priority == "reduce_risk":
            family_key = (-family_count,)
        else:
            family_key = (-family_count,
                          not any(c["group"] == "Leguminosae" for c in crops))
        # Prefer crops with no detected mismatch, then apply transparent goal-specific rules.
        risk_key = (sum(bool(x["screen"]["flagged"]) for x in seq),)
        if priority == "conserve_water":
            key = (*risk_key, *water_key, *family_key, ids)
        else:
            key = (*risk_key, *family_key, ids)
        options.append((key, [c["name"] for c in crops]))
    options.sort(key=lambda x: x[0])
    result = []
    for _, names in options:
        if names not in result:
            result.append(names)
        if len(result) == 2:
            break
    return result


def build_report(farm, inputs, summary, features, drafts):
    profile = farm.profile
    excluded = {resolve(n) for n in inputs.excludedCrops}
    priority = inputs.priority or profile.get("goal", "reduce_risk")
    previous = list(inputs.previousCrops)
    current = list(inputs.currentRotation or [profile["currentCrop"]])
    current_history = [*previous, *current]

    candidates = []
    screens = {}
    for c in CROPS:
        if c["id"] in excluded:
            continue
        reasons, risks, screen, flagged = _candidate_evidence(c, summary, features, inputs, inputs.plantingDate)
        status = "conditional_candidate"
        if screen["waterConflict"]:
            status = "water_budget_conflict_review"
        elif flagged:
            status = "reference_conflict_review"
        candidates.append({"crop": public_crop(c), "status": status, "reasons": reasons,
                           "risks": risks, "calendar": calendar_for(c, inputs.plantingDate),
                           "environmentalContext": screen["climate"],
                           "screen": {**screen, "flagged": flagged}})
        screens[c["id"]] = candidates[-1]

    ordered_candidates = list(candidates)
    if priority == "conserve_water":
        ordered_candidates.sort(key=lambda r: (
            r["screen"]["flagged"],
            r["crop"].get("waterMm") is None,
            r["crop"].get("waterMm", [float("inf")])[0],
            r["crop"]["name"].casefold()))
    else:
        ordered_candidates.sort(key=lambda r: (
            r["screen"]["flagged"],
            r["crop"]["name"].casefold()))
    # Keep the library order for display; alternatives use the explicit priority order.
    alternative_pool = ordered_candidates
    if inputs.availableSeasonalWaterMm is not None:
        # A numeric water constraint cannot support alternatives for crops with
        # no comparable reference requirement, nor for crops below its lower
        # bound. Do not infer missing demand from ECOCROP rainfall totals.
        alternative_pool = [c for c in ordered_candidates
                            if c["crop"].get("waterMm") and not c["screen"]["waterConflict"]]
    sequences = _alternative_sequences(alternative_pool, priority, previous, current)

    scenarios = [_scenario("current", "Current rotation (farmer reported)",
                           current_history, current, inputs.plantingDate,
                           previous, inputs.availableSeasonalWaterMm,
                           "farmer_reported_rotation")]
    draft_by_slot = {d.slot: d for d in drafts}
    for i, label in enumerate(("A", "B")):
        slot = "alternative_" + label.lower()
        draft = draft_by_slot.get(slot)
        if draft:
            names = draft.crops
            scenarios.append(_scenario(slot, draft.name + " (farmer draft)",
                                       [*previous[-1:], *current[-1:], *names], names,
                                       inputs.plantingDate, previous, inputs.availableSeasonalWaterMm,
                                       "farmer_saved_draft"))
        else:
            names = sequences[i] if len(sequences) > i else []
            display_names = [*previous[-1:], *current[-1:], *names] if names else []
            scenarios.append(_scenario(slot, "Alternative " + label + " — conditional rules",
                                       display_names, names,
                                       inputs.plantingDate, previous, inputs.availableSeasonalWaterMm))

    missing = []
    if not inputs.plantingDate:
        missing.append("A farmer-chosen hypothetical sowing date for calendar-window comparisons")
    if not inputs.previousCrops and profile.get("cropHistory"):
        missing.append("Structured chronological crop history; the free-text profile note was retained but not interpreted")
    elif not inputs.previousCrops:
        missing.append("Previous crops and their chronological order")
    if inputs.availableSeasonalWaterMm is None:
        missing.append("Quantified crop-available seasonal water; the irrigation category alone does not establish supply")
    if not summary.get("availableParameters"):
        missing.append("NASA observations for the exact selected coordinates")
    if any(c["screen"]["soilStatus"] == "missing" for c in candidates):
        missing.append("Farm-relevant soil pH and root-zone properties; no matching pH measurement was available")
    if any(c["screen"]["soilStatus"] == "proxy_only" for c in candidates):
        missing.append("Farm-validated soil tests; nearby SoilGrids proxy inputs are not farm measurements")
    if not any(c.get("waterMm") for c in CROPS if c["id"] not in excluded):
        missing.append("Comparable FAO crop-water ranges for the remaining selected crops")
    if not any(c["slot"] == "alternative_a" and c["crops"] for c in scenarios) or \
       not any(c["slot"] == "alternative_b" and c["crops"] for c in scenarios):
        missing.append("More non-excluded crops with distinct botanical families for two defensible alternatives")
    constraints = [profile.get(k, "") for k in ("waterConstraints", "waterResources", "agriculturalConstraints")]
    constraints = [x for x in constraints + [inputs.operationalLimitations] if x]
    management = [
        finding("rotation_design", "Choose the crop sequence against a stated goal, local soil/climate, water availability and pest concern. The current report does not quantify soil-health or yield outcomes.",
                "usda_nrcs_rotation", "fao_diversification"),
        finding("soil_cover", "Assess locally adapted cover or residue options for erosion protection and soil cover. Check water competition, termination, pests, livestock use and equipment before adopting.",
                "usda_nrcs_cover", "fao_conservation"),
        finding("disturbance", "Consider reduced disturbance only with local weed, soil-condition, equipment and conservation-practice review.",
                "fao_conservation"),
        finding("water_management", "Use crop-stage water balance, effective rainfall, root-zone storage, irrigation delivery and local evapotranspiration for a water plan. This report does not prescribe irrigation depth or frequency.",
                "usda_nrcs_rotation", "fao_water_manual"),
    ]
    if profile.get("soilType"):
        management.append(finding("farmer_soil_type", f"Farmer-described soil type ({profile['soilType']}) is retained as an input but is not mapped to a verified texture or drainage class.",
                                  "fao_ecocrop"))
    if constraints:
        management.append(finding("operational_constraints", "Recorded farm constraints require human review; this rules engine does not infer equipment, market, labor, or water feasibility from free text."))

    warnings = [
        *LIMITATIONS,
        "Candidate labels describe possible reference-range conflicts only. 'No conflict detected' is not evidence of crop suitability.",
        "NASA data influence the planning screen only through historical monthly temperature context; rainfall and GWETTOP/GWETROOT are preserved as provenance, not treated as effective rainfall or field soil moisture.",
        "Alternative sequences are deterministic rule-based options, not yield, profitability, risk, or suitability rankings.",
        "Saved manual rotation drafts are included as farmer-authored scenarios and are not silently corrected.",
    ]
    if priority == "productivity":
        warnings.append("Productivity priority is recorded, but no yield or profitability evidence exists to optimize for it.")
    if priority == "reduce_risk":
        warnings.append("Risk ordering only avoids same-family adjacency and reference-screen flags. It is not a pest or disease-risk model.")
    return {"farmId": farm.id, "createdAt": datetime.now(timezone.utc).isoformat(),
            "knowledgeVersion": VERSION, "engineVersion": ENGINE_VERSION,
            "status": "reference_based_plan" if sequences and summary.get("availableParameters") else "insufficient_evidence",
            "modelStatus": "not_trained",
            "inputs": {"planning": {**inputs.model_dump(mode="json"), "priority": priority},
                       "farmerProfile": deepcopy(profile),
                       "sources": {"farmerProfile": "farmer_reported_unverified",
                                   "planning": "farmer_reported_scenario_assumptions"},
                       "savedManualDrafts": [{"slot": d.slot, "name": d.name, "crops": d.crops, "notes": d.notes} for d in drafts]},
            "priorityApplied": priority,
            "candidates": candidates, "scenarios": scenarios, "management": management,
            "missingInformation": missing, "warnings": list(dict.fromkeys(warnings + summary.get("warnings", []))),
            "references": deepcopy(REFERENCES),
            "environmentalEvidence": {"location": summary.get("location"), "status": summary.get("status"),
                "referencePeriod": summary.get("referencePeriod"), "parameters": summary.get("availableParameters", []),
                "provenance": summary.get("provenance", []), "soilInputs": features.get("soilInputs", {}),
                "annual": summary.get("annual", []), "irrigation": features.get("irrigation"),
                "note": "NASA POWER exact-coordinate climate and modelled wetness are source-tagged context only. GWETTOP/GWETROOT are not SMAP or field soil measurements. Proxy soil values are never ground truth or suitability proof."}}
