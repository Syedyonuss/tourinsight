"""Transparent lightweight lexicon sentiment analysis for feedback; no black-box labels."""
from __future__ import annotations
import re
from collections import Counter
from typing import Any
from backend.db import connect

POSITIVE = {"beautiful","amazing","excellent","great","good","wonderful","clean","friendly","helpful","safe","peaceful","scenic","lovely","enjoyed","enjoyable","memorable","comfortable","delicious","best","recommend","easy","well-maintained","fantastic","superb","pleasant","awesome","calm","fascinating"}
NEGATIVE = {"bad","poor","dirty","unsafe","crowded","overcrowded","expensive","rude","difficult","delay","delayed","broken","unhygienic","disappointing","disappointed","worst","terrible","noisy","waste","inconvenient","damaged","closed","unavailable","traffic","overpriced","unfriendly","uncomfortable","limited"}
ASPECTS = {
    "cleanliness": ["clean","dirty","litter","garbage","toilet","washroom","hygiene","sanitation"],
    "transport": ["transport","bus","train","taxi","road","traffic","parking","connectivity","commute"],
    "accommodation": ["hotel","stay","room","resort","homestay","accommodation","hostel"],
    "safety": ["safe","unsafe","security","theft","crowd","harassment","lighting"],
    "cost and value": ["price","cost","expensive","cheap","budget","overpriced","ticket","fee"],
    "facilities": ["facility","facilities","signage","water","food","restaurant","guide","queue"],
}


def analyse_text(text: str) -> tuple[str, list[str]]:
    tokens = re.findall(r"[a-z][a-z'-]+", (text or "").lower())
    pos = sum(1 for t in tokens if t in POSITIVE)
    neg = sum(1 for t in tokens if t in NEGATIVE)
    sentiment = "positive" if pos > neg else "negative" if neg > pos else "neutral"
    low = (text or "").lower()
    aspects = [name for name, terms in ASPECTS.items() if any(term in low for term in terms)]
    return sentiment, aspects


def dashboard_sentiment() -> dict[str, Any]:
    with connect() as conn:
        rows = conn.execute("SELECT r.*,d.name destination FROM reviews r JOIN destinations d ON d.id=r.destination_id ORDER BY r.review_date DESC").fetchall()
    if not rows:
        return {"available": False, "total": 0, "message": "No visitor feedback has been collected yet. Submit feedback or import a properly licensed review dataset to enable this analysis."}
    sentiments = Counter()
    aspects = Counter()
    destination_scores: dict[str, list[float]] = {}
    cleaned = []
    for r in rows:
        sentiment, found = analyse_text(r["review_text"])
        sentiments[sentiment] += 1
        aspects.update(found)
        if r["rating"] is not None:
            destination_scores.setdefault(r["destination"], []).append(float(r["rating"]))
        cleaned.append({"id":r["id"],"destination":r["destination"],"author":r["author"],"rating":r["rating"],"text":r["review_text"],"date":r["review_date"],"sentiment":sentiment,"aspects":found,"source":r["source"],"image_url":r["image_url"] if "image_url" in r.keys() else None})
    avg_rating = sum(float(r["rating"]) for r in rows if r["rating"] is not None) / max(1, sum(1 for r in rows if r["rating"] is not None))
    return {"available": True, "total": len(rows), "sentiments": dict(sentiments), "aspects": dict(aspects),
            "average_rating": round(avg_rating, 2) if any(r["rating"] is not None for r in rows) else None,
            "destination_ratings": {k:round(sum(v)/len(v),2) for k,v in destination_scores.items()}, "reviews": cleaned[:100],
            "method":"Transparent English keyword lexicon with aspect-term matching. It is an indicative baseline, not a trained domain-specific sentiment model."}
