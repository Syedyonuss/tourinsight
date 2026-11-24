"""Local smoke test for TourInsight. Run: python tests/smoke_test.py"""
from __future__ import annotations
import os
import tempfile
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

_tmp = tempfile.TemporaryDirectory(prefix="tourinsight-test-")
os.environ["TOURINSIGHT_DB"] = str(Path(_tmp.name) / "test.db")
os.environ["SESSION_SECRET"] = "tourinsight-smoke-test-session-secret-123456"

from fastapi.testclient import TestClient
from backend.main import APP
from backend.db import connect, init_db
import backend.services.recommendations as recommendation_service
import backend.services.itinerary as itinerary_service


async def mock_climate(destination, month):
    return {
        "available": True, "score": 82.0, "avg_max_c": 29.0, "avg_min_c": 20.0,
        "wet_days_pct": 15.0, "period": "2016–2025", "source": "Test fixture",
        "basis": "Test fixture only",
    }


async def mock_route(points):
    legs = [{"distance_km": 85.0, "duration_hours": 2.0} for _ in range(max(0, len(points) - 1))]
    return {
        "source": "Test routing fixture", "legs": legs,
        "geometry": {"type": "LineString", "coordinates": [[lon, lat] for lat, lon in points]},
    }


recommendation_service.monthly_climate = mock_climate
itinerary_service.route_geometry = mock_route


def main() -> int:
    checks: list[tuple[str, bool]] = []

    def check(name: str, condition: bool) -> None:
        checks.append((name, bool(condition)))
        print(f"{'PASS' if condition else 'FAIL'}  {name}")

    with TestClient(APP) as client:
        check("health endpoint", client.get("/api/health").status_code == 200)
        destinations = client.get("/api/destinations").json()["destinations"]
        check("10 Karnataka destinations seeded", len(destinations) == 10)
        check("dashboard loads", client.get("/api/dashboard").status_code == 200)
        check("application metadata loads", client.get("/api/meta").status_code == 200)
        check("data quality summary loads", client.get("/api/quality").status_code == 200)
        check("forecast stays inactive without visitor time series", client.get("/api/predictions").json()["available_count"] == 0)

        preferences = {
            "origin": "Hyderabad, Telangana", "region": "Any region", "month": 11,
            "interests": ["nature and hill stations", "historical and heritage tourism"],
            "budget": 60000, "days": 4, "travellers": 2, "group": "family",
        }
        rec = client.post("/api/recommendations", json=preferences)
        check("SmartSeason returns top five ranked destinations", rec.status_code == 200 and len(rec.json().get("results", [])) == 5)
        if rec.status_code == 200 and rec.json().get("results"):
            target_slug = rec.json()["results"][0]["slug"]
            alternatives = client.post("/api/alternatives", json={**preferences, "target_slug": target_slug})
            check("alternative destination discovery", alternatives.status_code == 200 and bool(alternatives.json().get("alternatives")))
        else:
            check("alternative destination discovery", False)

        route = client.post("/api/itineraries/custom-preview", json={
            "origin": "Bengaluru", "month": 11, "travellers": 2,
            "destination_slugs": ["mysuru", "coorg"],
        })
        check("custom multi-destination route preview", route.status_code == 200 and len(route.json().get("days", [])) == 2)

        register = client.post("/api/auth/register", json={
            "email": "tourist@example.com", "full_name": "Smoke Test Tourist",
            "password": "TourInsight!234", "origin": "Bengaluru",
        })
        check("user registration", register.status_code == 200)
        check("session-backed profile", client.get("/api/auth/me").json().get("user", {}).get("email") == "tourist@example.com")

        save = client.post("/api/itineraries/save-preview", json={"title": "Test route", "plan": route.json()})
        check("save itinerary", save.status_code == 200)
        check("retrieve saved itinerary", len(client.get("/api/itineraries").json().get("itineraries", [])) == 1)
        shared = client.post(f"/api/itineraries/{save.json()['id']}/share")
        check("create public itinerary share link", shared.status_code == 200 and "/shared/" in shared.json().get("url", ""))
        check("public itinerary share page renders", client.get(shared.json()["url"]).status_code == 200)
        post = client.post("/api/community/posts", json={"title":"Coorg field note", "body":"Start the viewpoint walk early and carry drinking water.", "destination_slug":"coorg", "post_type":"tip"})
        check("publish community travel tip", post.status_code == 200 and len(client.get("/api/community/posts").json()["posts"]) == 1)
        journal = client.post("/api/journal", json={"title":"Coorg weekend", "destination_slug":"coorg", "visit_date":"2026-11-24", "notes":"Misty morning and quiet coffee estate roads."})
        check("save personal travel journal entry", journal.status_code == 200 and len(client.get("/api/journal").json()["entries"]) == 1)
        checkin = client.post("/api/checkins", json={"destination_slug":"coorg", "visited_on":"2026-11-24", "note":"First visit"})
        check("record destination passport check-in", checkin.status_code == 200 and client.get("/api/challenges").json()["visited_count"] == 1)
        group = client.post("/api/groups", json={"name":"Weekend travel crew"})
        check("create collaborative trip group", group.status_code == 200 and bool(group.json().get("invite_code")))
        group_id = group.json().get("id")
        suggestion = client.post(f"/api/groups/{group_id}/suggestions", json={"destination_slug":"mysuru", "note":"Good heritage stop for the group."})
        check("add a destination to group planning board", suggestion.status_code == 200)
        vote = client.post(f"/api/groups/{group_id}/suggestions/{suggestion.json().get('id')}/vote", json={})
        check("vote on group destination suggestion", vote.status_code == 200 and vote.json().get("voted") is True)
        check("transport provider shortcuts load", client.get("/api/transport/coorg").status_code == 200)
        check("emergency information loads", client.get("/api/emergency").json()["contacts"][0]["number"] == "112")

        with connect() as conn:
            conn.execute("UPDATE users SET role='admin' WHERE email='tourist@example.com'")
            conn.commit()
        check("administrator overview and access control", client.get("/api/admin/overview").status_code == 200)
        connector_status = client.get("/api/admin/connectors/data-gov-in/status")
        check("data.gov.in connector status is administrator-protected and reports configuration", connector_status.status_code == 200 and connector_status.json().get("configured") is False)
        unconfigured_sync = client.post("/api/admin/connectors/data-gov-in/sync")
        check("data.gov.in sync gives a clear setup error when credentials are absent", unconfigured_sync.status_code == 400 and "DATA_GOV_IN_API_KEY" in unconfigured_sync.json().get("detail", ""))

        tourism_csv = (
            "destination,year,month,visitors,capacity_per_month\n"
            "Mysuru,2024,1,12000,50000\nMysuru,2024,2,14000,50000\n"
        )
        tourism_import = client.post("/api/admin/import/tourism-stats", data={"source_name": "Smoke test tourism source"},
                                     files={"file": ("stats.csv", tourism_csv, "text/csv")})
        check("tourism CSV import", tourism_import.status_code == 200 and tourism_import.json().get("inserted") == 2)

        reviews_csv = (
            "destination,review,rating,author,date\n"
            'Mysuru,"Beautiful clean place and friendly guides",5,Tester,2024-01-01\n'
        )
        reviews_import = client.post("/api/admin/import/reviews", data={"source_name": "Smoke test licensed reviews"},
                                     files={"file": ("reviews.csv", reviews_csv, "text/csv")})
        check("review CSV import and sentiment tagging", reviews_import.status_code == 200 and reviews_import.json().get("inserted") == 1)
        dashboard = client.get("/api/dashboard")
        check("weighted visitor rating aggregation", dashboard.status_code == 200 and dashboard.json()["kpis"]["avg_rating"] == 5.0)

        with connect() as conn:
            destination_id = conn.execute("SELECT id FROM destinations WHERE slug='mysuru'").fetchone()["id"]
            for year in (2022, 2023):
                for month in range(1, 13):
                    visitors = 10000 + month * 100 + (year - 2022) * 500
                    conn.execute(
                        "INSERT OR REPLACE INTO tourism_stats(destination_id,year,month,visitors) VALUES(?,?,?,?)",
                        (destination_id, year, month, visitors),
                    )
            conn.commit()
        forecasts = client.get("/api/predictions").json()
        mysuru_forecast = next(item for item in forecasts["destinations"] if item["slug"] == "mysuru")
        check("ML forecast activates at 24 monthly observations", mysuru_forecast["available"] and len(mysuru_forecast["forecast"]) == 3 and bool(mysuru_forecast["model_scores"]))

        check("admin quality report", client.get("/api/admin/quality").status_code == 200)
        check("admin recommendation weights", client.get("/api/admin/weights").status_code == 200)

        # Ensure reference seeding on application restart does not overwrite admin edits.
        with connect() as conn:
            conn.execute("UPDATE destinations SET popularity_index=17 WHERE slug='mysuru'")
            conn.commit()
        init_db()
        with connect() as conn:
            popularity = conn.execute("SELECT popularity_index FROM destinations WHERE slug='mysuru'").fetchone()[0]
        check("admin destination edits persist across restarts", popularity == 17)

        check("logout", client.post("/api/auth/logout").status_code == 200)

    passed = sum(ok for _, ok in checks)
    print(f"\nSmoke test result: {passed}/{len(checks)} passed")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
