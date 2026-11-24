"""Database-backed analytics; missing data stays missing instead of being fabricated."""
from __future__ import annotations
import math
from typing import Any
from backend.db import connect, destination_dict
from backend.services.sentiment import dashboard_sentiment


def opportunity_score(dest: dict[str, Any], rating: dict[str, Any] | None, pressure: dict[str, Any]) -> dict[str, Any]:
    values = {"popularity": float(dest.get("popularity_index") or 0),
              "satisfaction": (float(rating["avg"]) / 5 * 100) if rating else None,
              "accessibility": float(dest.get("accessibility_score") or 0),
              "pressure": (100 - min(100, float(pressure["ratio"]) * 100)) if pressure.get("available") else None}
    weights = {"popularity":.25,"satisfaction":.30,"accessibility":.20,"pressure":.25}
    available = {k:v for k,v in values.items() if v is not None}
    denominator = sum(weights[k] for k in available)
    score = round(sum(values[k]*weights[k] for k in available)/denominator,1) if denominator else None
    return {"score":score,"coverage":round(denominator*100),"components":values,
            "note":"Partial score; weights are re-normalized over available inputs. Popularity and accessibility are editorial baselines; satisfaction comes from stored reviews; pressure requires imported visitor data and a documented capacity."}


def pressure_for(conn, destination_id: int, capacity: float | None) -> dict[str, Any]:
    row = conn.execute("SELECT year,month,visitors FROM tourism_stats WHERE destination_id=? ORDER BY year DESC,month DESC LIMIT 1",(destination_id,)).fetchone()
    if not row:
        return {"available":False,"label":"Not enough data"}
    if not capacity or capacity <= 0:
        return {"available":False,"label":"Capacity baseline missing","visitors":row["visitors"],"year":row["year"],"month":row["month"]}
    ratio = row["visitors"] / capacity
    label = "High" if ratio >= .8 else "Moderate" if ratio >= .5 else "Lower"
    return {"available":True,"label":label,"ratio":round(ratio,3),"visitors":row["visitors"],"capacity":capacity,"year":row["year"],"month":row["month"],"note":"Imported monthly visitors ÷ destination monthly capacity. This is an estimated pressure indicator, not a live crowd count."}


def dashboard_data() -> dict[str, Any]:
    with connect() as conn:
        dest_rows = conn.execute("SELECT * FROM destinations WHERE active=1 ORDER BY name").fetchall()
        stats = conn.execute("SELECT year,month,SUM(visitors) visitors FROM tourism_stats GROUP BY year,month ORDER BY year,month").fetchall()
        reviews_count = conn.execute("SELECT COUNT(*) n FROM reviews").fetchone()["n"]
        sources = conn.execute("SELECT name,status,last_updated FROM data_sources ORDER BY category,name").fetchall()
        month_rows = conn.execute("SELECT month,AVG(score) score FROM seasonal_suitability GROUP BY month ORDER BY month").fetchall()
        ratings_rows = conn.execute("SELECT destination_id,AVG(rating) rating,COUNT(*) n FROM reviews WHERE rating IS NOT NULL GROUP BY destination_id").fetchall()
        ratings = {r["destination_id"]:{"avg":round(float(r["rating"]),2),"count":r["n"]} for r in ratings_rows}
        destinations = [destination_dict(r) for r in dest_rows]
        items=[]
        for d in destinations:
            pressure = pressure_for(conn, d["id"], d["capacity_per_month"])
            opp = opportunity_score(d, ratings.get(d["id"]), pressure)
            series = conn.execute("SELECT year,month,visitors FROM tourism_stats WHERE destination_id=? ORDER BY year,month",(d["id"],)).fetchall()
            trend = {"available":False,"label":"Insufficient history"}
            if len(series) >= 6:
                previous = [float(x["visitors"]) for x in series[-6:-3]]
                recent = [float(x["visitors"]) for x in series[-3:]]
                baseline = sum(previous)/len(previous)
                pct = ((sum(recent)/len(recent)-baseline)/baseline*100) if baseline else None
                if pct is not None:
                    trend = {"available":True,"change_pct":round(pct,1),"label":"Emerging" if pct>=10 else "Declining" if pct<=-10 else "Stable",
                             "basis":"Latest three imported monthly observations versus the previous three."}
            items.append({"slug":d["slug"],"name":d["name"],"district":d["district"],"region":d["region"],"category":d["category"],
                          "popularity_index":d["popularity_index"],"rating":ratings.get(d["id"]),"pressure":pressure,"opportunity":opp,"trend":trend})
    items.sort(key=lambda x: x["popularity_index"] or 0, reverse=True)
    return {"kpis":{"destinations":len(destinations),"tourism_records":len(stats),"review_count":reviews_count,
                    "avg_rating":round(sum(r["avg"]*r["count"] for r in ratings.values())/max(1,sum(r["count"] for r in ratings.values())),2) if ratings else None},
            "popularity_ranking":items,"monthly_tourism":[dict(r) for r in stats],"seasonality":[dict(r) for r in month_rows],
            "sentiment":dashboard_sentiment(),"sources":[dict(r) for r in sources],
            "analytics_notes":["The Karnataka destination catalogue is available locally.",
              "Popularity index is a curated discoverability baseline, not a count of visitors.",
              "Tourism time-series charts appear only after real monthly visitor data is imported.",
              "Review-based satisfaction appears only after user feedback or licensed review data is added."]}
