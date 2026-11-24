"""Inspectable data-quality checks across the local TourInsight database."""
from __future__ import annotations
from datetime import datetime, timezone
from backend.db import connect


def build_report() -> dict:
    now = datetime.now(timezone.utc)
    with connect() as conn:
        dest = conn.execute("SELECT * FROM destinations WHERE active=1").fetchall()
        stats = conn.execute("SELECT * FROM tourism_stats").fetchall()
        reviews = conn.execute("SELECT * FROM reviews").fetchall()
        sources = conn.execute("SELECT * FROM data_sources").fetchall()
        dup_stats = conn.execute("SELECT COUNT(*) n FROM (SELECT destination_id,year,month,COUNT(*) c FROM tourism_stats GROUP BY destination_id,year,month HAVING c>1)").fetchone()["n"]
        duplicate_reviews = conn.execute("SELECT COUNT(*) n FROM (SELECT destination_id,LOWER(TRIM(review_text)) normalized,source,COUNT(*) c FROM reviews GROUP BY destination_id,normalized,source HAVING c>1)").fetchone()["n"]
        duplicate_names = conn.execute("SELECT LOWER(REPLACE(REPLACE(REPLACE(name,' ',''),'-',''),'.','')) normalized,COUNT(*) c,GROUP_CONCAT(name) names FROM destinations GROUP BY normalized HAVING c>1").fetchall()
        missing_dest = []
        for d in dest:
            missing = [k for k in ("district", "region", "latitude", "longitude", "description", "budget_low", "budget_high") if d[k] is None or d[k] == ""]
            if missing: missing_dest.append({"destination": d["name"], "fields": missing})
        missing_source_urls = [s["name"] for s in sources if not s["url"] and s["category"] not in ("Reviews", "Destination metadata")]
        stale_sources = []
        for s in sources:
            if not s["last_updated"]: continue
            try:
                stamp = datetime.fromisoformat(s["last_updated"].replace("Z", "+00:00"))
                if stamp.tzinfo is None: stamp = stamp.replace(tzinfo=timezone.utc)
                if (now - stamp).days > 730: stale_sources.append(s["name"])
            except Exception: pass
        latest = max(((int(r["year"]), int(r["month"])) for r in stats), default=None)
        latest_period = f"{latest[0]}-{latest[1]:02d}" if latest else None
        visitor_data_outdated = False
        if latest:
            month_age = (now.year - latest[0]) * 12 + (now.month - latest[1])
            visitor_data_outdated = month_age > 18
        missing_review_dates = sum(1 for r in reviews if not r["review_date"])
        total_rows = len(stats) + len(reviews) + len(dest)
        issue_count = len(missing_dest) + dup_stats + duplicate_reviews + len(missing_source_urls) + len(stale_sources) + missing_review_dates + len(duplicate_names)
        completeness_score = max(0, 100 - round(issue_count / max(1, total_rows) * 100))
        return {
            "generated_at": now.isoformat(),
            "summary": {"destinations": len(dest), "tourism_records": len(stats), "reviews": len(reviews), "sources": len(sources),
                        "quality_score": completeness_score, "latest_visitor_period": latest_period,
                        "visitor_series_outdated": visitor_data_outdated},
            "checks": {"missing_destination_fields": missing_dest, "duplicate_tourism_months": dup_stats,
                       "duplicate_review_groups": duplicate_reviews,
                       "duplicate_or_inconsistent_destination_names": [dict(x) for x in duplicate_names],
                       "source_urls_missing": missing_source_urls, "source_records_not_refreshed_over_2_years": stale_sources,
                       "latest_visitor_data_period": latest_period, "visitor_series_older_than_18_months": visitor_data_outdated,
                       "reviews_missing_dates": missing_review_dates},
            "notes": ["The quality score is a simple completeness/consistency proxy, not a formal certification or measure of statistical accuracy.",
                      "Visitor-series freshness is checked from the latest year/month in the imported observations, not the local upload timestamp.",
                      "Tourism statistics and reviews should include dataset-level licence and source documentation before publication.",
                      "The local Karnataka destination catalogue is manually curated and should be verified against official destination sources."]
        }
