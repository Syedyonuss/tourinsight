"""Explainable, weighted SmartSeason recommendation engine."""
from __future__ import annotations
import json, asyncio
from typing import Any
from backend.db import connect, destination_dict
from backend.services.weather import monthly_climate

INTERESTS = ["nature and hill stations", "historical and heritage tourism", "beaches",
             "adventure and trekking", "religious tourism", "wildlife and forests", "family sightseeing"]


def _budget_score(budget: float, low: float, high: float, days: int, people: int) -> float:
    need_low = max(1, low * days * people)
    need_high = max(need_low, high * days * people)
    if budget >= need_high: return 100.0
    if budget >= need_low: return 82.0 + 18.0 * (budget - need_low) / max(1, need_high - need_low)
    return max(0.0, 82.0 * budget / need_low)


def _interest_score(selected: list[str], destination: dict[str, Any]) -> float:
    if not selected: return 65.0
    available = set(destination["interests"]) | set(destination["tags"])
    matches = 0
    for item in selected:
        normalized = item.lower().strip()
        if normalized in available or any(normalized in x or x in normalized for x in available):
            matches += 1
    return round(100 * matches / len(selected), 1)


def _crowd_info(conn, dest_id: int, month: int) -> dict[str, Any]:
    row = conn.execute("""SELECT s.visitors,s.year,s.month,d.capacity_per_month FROM tourism_stats s
        JOIN destinations d ON d.id=s.destination_id WHERE s.destination_id=? AND s.month=?
        ORDER BY s.year DESC LIMIT 1""", (dest_id, month)).fetchone()
    if not row:
        return {"available": False, "label": "Insufficient verified visitor data", "note": "No destination-level monthly visitor series has been imported."}
    if not row["capacity_per_month"] or row["capacity_per_month"] <= 0:
        return {"available": False, "label": "Visitor data available; capacity not recorded", "visitors": row["visitors"], "year": row["year"], "note": "Pressure cannot be calculated without a documented capacity baseline."}
    ratio = row["visitors"] / row["capacity_per_month"]
    label = "High pressure" if ratio >= .8 else "Moderate pressure" if ratio >= .5 else "Lower pressure"
    return {"available": True, "label": label, "visitors": row["visitors"], "capacity": row["capacity_per_month"], "year": row["year"], "ratio": round(ratio,2), "note": "Estimated from imported monthly visitors divided by admin-recorded monthly capacity; not live crowd counts."}


async def generate_recommendations(payload: dict[str, Any]) -> dict[str, Any]:
    month = int(payload["month"])
    selected = [str(x).lower().strip() for x in payload.get("interests", [])]
    budget = float(payload.get("budget", 0))
    days = int(payload.get("days", 3))
    people = int(payload.get("travellers", 1))
    region = payload.get("region", "Any region")
    with connect() as conn:
        rows = conn.execute("SELECT * FROM destinations WHERE active=1 ORDER BY name").fetchall()
        weights = {r["key"]: float(r["value"]) for r in conn.execute("SELECT key,value FROM recommendation_weights")}
        review_rows = conn.execute("SELECT destination_id,AVG(rating) rating,COUNT(*) total FROM reviews WHERE rating IS NOT NULL GROUP BY destination_id").fetchall()
        ratings = {r["destination_id"]: {"avg": round(float(r["rating"]),2), "count": r["total"]} for r in review_rows}
        seasonal_rows = conn.execute("SELECT destination_id,month,score,label FROM seasonal_suitability WHERE month=?", (month,)).fetchall()
        seasonal = {r["destination_id"]: dict(r) for r in seasonal_rows}
        dests = [destination_dict(r) for r in rows]
        if region and region != "Any region":
            dests = [d for d in dests if d["region"] == region or d["district"] == region]
        climate_results = await asyncio.gather(*(monthly_climate(d, month) for d in dests), return_exceptions=True)
        scored = []
        for d, climate in zip(dests, climate_results):
            if isinstance(climate, Exception):
                climate = {"available": False, "score": None, "error": str(climate)[:180],
                           "basis": "Historical climate data unavailable; weather weight is excluded."}
            seasonal_row = seasonal.get(d["id"])
            season = float(seasonal_row["score"]) if seasonal_row else 50.0
            weather_score = climate.get("score") if climate.get("available") else None
            interest = _interest_score(selected, d)
            popularity = float(d["popularity_index"] or 50)
            budget_score = _budget_score(budget, float(d["budget_low"] or 1), float(d["budget_high"] or d["budget_low"] or 1), days, people) if budget > 0 else 65.0
            accessibility = float(d["accessibility_score"] or 50)
            values = {"seasonal":season,"weather":weather_score,"interest":interest,"popularity":popularity,"budget":budget_score,"accessibility":accessibility}
            used = {k:v for k,v in values.items() if v is not None and k in weights and weights[k] > 0}
            denominator = sum(weights[k] for k in used)
            score = round(sum(used[k] * weights[k] for k in used) / denominator, 1) if denominator else 0.0
            reasons = []
            if season >= 80: reasons.append(f"{seasonal_row['label'] if seasonal_row else 'Seasonal fit'} for {d['name']} in month {month}.")
            if weather_score is not None: reasons.append(f"Historical climate conditions score {weather_score}/100 ({climate.get('period')}).")
            matched = [x for x in selected if _interest_score([x], d) >= 99]
            if matched: reasons.append("Matches your interests: " + ", ".join([x.title() for x in matched]) + ".")
            if budget_score >= 80: reasons.append("Indicative trip budget is within or close to the selected budget.")
            if not reasons: reasons.append("A reasonable overall match based on the selected month, interests and trip constraints.")
            disadvantages = []
            if season < 55: disadvantages.append("The selected month is outside the usual preferred visiting window.")
            if budget_score < 55: disadvantages.append("The selected budget may be tight for this destination and trip length.")
            if d["slug"] in ("coorg","chikkamagaluru","kabini") and month in (6,7,8,9): disadvantages.append("Heavy monsoon conditions may affect outdoor plans; check current alerts and access.")
            if not climate.get("available"): disadvantages.append("Historical climate feed is currently unavailable; weather is excluded from the score.")
            crowd = _crowd_info(conn, d["id"], month)
            rating = ratings.get(d["id"])
            scored.append({"id":d["id"],"slug":d["slug"],"name":d["name"],"district":d["district"],"region":d["region"],"category":d["category"],"image":d["image_url"],
                "score":score,"score_breakdown":values,"weights_used":{k:weights[k] for k in used},"score_coverage":round(denominator,1),
                "reasons":reasons,"disadvantages":disadvantages,"weather":climate,"season_label":seasonal_row["label"] if seasonal_row else "Seasonal guidance unavailable",
                "season_score":season,"budget_low":d["budget_low"],"budget_high":d["budget_high"],"visit_days":d["visit_days"],"accessibility":d["accessibility_score"],
                "attractions":d["attractions"],"description":d["description"],"season_note":d["season_note"],"crowd":crowd,
                "rating":rating,"interests":d["interests"],"latitude":d["latitude"],"longitude":d["longitude"]})
    scored.sort(key=lambda x: x["score"], reverse=True)
    top = scored[:5]
    return {"results":top,"all_results":scored,"month":month,"weights":weights,"method":"Weighted additive model; available factors are re-normalized to 100 when a connected source is unavailable.",
            "data_notes":["Popularity uses an explicitly labelled local editorial discoverability baseline, not official visitor counts.",
                          "Budget and accessibility fields are indicative planning estimates and should be validated before travel.",
                          "Historical climate comes from Open-Meteo ERA5/ERA5-Land reanalysis when available; it is not a date-specific forecast.",
                          "Tourism pressure is only computed when monthly visitor statistics and a documented capacity value are both present."]}
