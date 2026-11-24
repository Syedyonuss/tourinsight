"""SQLite persistence, schema initialization and Karnataka reference catalogue."""
from __future__ import annotations
import json
import os
import sqlite3
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = Path(os.getenv("TOURINSIGHT_DB", str(ROOT / "database" / "tourinsight.db")))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

DESTINATIONS: list[dict[str, Any]] = [
    {"slug":"bengaluru","name":"Bengaluru","district":"Bengaluru Urban","region":"South Karnataka","lat":12.9716,"lon":77.5946,"category":"City & Culture","tags":["family","food","culture","shopping","technology","heritage"],"interests":["family sightseeing","historical and heritage tourism"],"description":"Karnataka's capital blends historic landmarks, gardens, museums, food districts and a lively contemporary culture.","attractions":["Lalbagh Botanical Garden","Bengaluru Palace","Cubbon Park","Vidhana Soudha","National Gallery of Modern Art"],"best_months":[1,2,3,11,12],"budget_low":2200,"budget_high":6500,"visit_days":2,"accessibility":96,"popularity":94,"image":"https://images.unsplash.com/photo-1596176530529-78163a4f7af2?auto=format&fit=crop&w=1200&q=85","season_note":"Generally easier for city sightseeing in the cooler months; hot afternoons are common before the monsoon."},
    {"slug":"mysuru","name":"Mysuru","district":"Mysuru","region":"South Karnataka","lat":12.2958,"lon":76.6394,"category":"Heritage & Culture","tags":["heritage","palace","culture","family","religious"],"interests":["historical and heritage tourism","religious tourism","family sightseeing"],"description":"A heritage city known for its palace, traditional markets, yoga culture and nearby cultural attractions.","attractions":["Mysore Palace","Chamundi Hill","St. Philomena's Church","Jaganmohan Palace","Brindavan Gardens"],"best_months":[1,2,3,10,11,12],"budget_low":2000,"budget_high":5500,"visit_days":2,"accessibility":91,"popularity":90,"image":"https://images.unsplash.com/photo-1600100599028-6f5c7b9b4c3b?auto=format&fit=crop&w=1200&q=85","season_note":"October to March is a common comfortable window for outdoor sightseeing."},
    {"slug":"coorg","name":"Coorg (Kodagu)","district":"Kodagu","region":"Western Ghats","lat":12.4244,"lon":75.7382,"category":"Hill Station & Nature","tags":["nature","hills","coffee","waterfalls","trekking","wildlife"],"interests":["nature and hill stations","adventure and trekking","wildlife and forests"],"description":"A Western Ghats hill region of coffee estates, forest landscapes, waterfalls and scenic viewpoints.","attractions":["Abbey Falls","Raja's Seat","Dubare Elephant Camp","Mandalpatti Viewpoint","Coffee Estate Walks"],"best_months":[1,2,3,10,11,12],"budget_low":2800,"budget_high":7500,"visit_days":3,"accessibility":68,"popularity":88,"image":"https://images.unsplash.com/photo-1511497584788-876760111969?auto=format&fit=crop&w=1200&q=85","season_note":"Post-monsoon through winter is commonly preferred; heavy monsoon rain can disrupt outdoor activities."},
    {"slug":"hampi","name":"Hampi","district":"Vijayanagara","region":"North Karnataka","lat":15.3350,"lon":76.4600,"category":"Heritage & Archaeology","tags":["heritage","history","architecture","cycling","culture"],"interests":["historical and heritage tourism","adventure and trekking"],"description":"A UNESCO-listed archaeological landscape featuring the remains of the Vijayanagara Empire among dramatic boulder-strewn terrain.","attractions":["Virupaksha Temple","Vittala Temple Complex","Stone Chariot","Hampi Bazaar","Matanga Hill"],"best_months":[1,2,10,11,12],"budget_low":1800,"budget_high":5200,"visit_days":2,"accessibility":65,"popularity":91,"image":"https://images.unsplash.com/photo-1606293926075-69a00dbfde81?auto=format&fit=crop&w=1200&q=85","season_note":"October to February is generally more comfortable for walking among the monuments; summer heat can be intense."},
    {"slug":"gokarna","name":"Gokarna","district":"Uttara Kannada","region":"Coastal Karnataka","lat":14.5479,"lon":74.3188,"category":"Beach & Coastal","tags":["beach","coast","temple","trekking","relaxation"],"interests":["beaches","adventure and trekking","religious tourism"],"description":"A coastal town combining beaches, coastal walks and an important pilgrimage setting.","attractions":["Om Beach","Kudle Beach","Half Moon Beach","Mahabaleshwar Temple","Mirjan Fort"],"best_months":[1,2,3,10,11,12],"budget_low":2200,"budget_high":6500,"visit_days":2,"accessibility":62,"popularity":86,"image":"https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=1200&q=85","season_note":"Beach activities are usually more practical outside the southwest monsoon period."},
    {"slug":"chikkamagaluru","name":"Chikkamagaluru","district":"Chikkamagaluru","region":"Western Ghats","lat":13.3161,"lon":75.7720,"category":"Hill Station & Nature","tags":["nature","hills","coffee","trekking","waterfalls"],"interests":["nature and hill stations","adventure and trekking"],"description":"A highland region of coffee plantations, mountain roads, viewpoints and trekking routes in the Western Ghats.","attractions":["Mullayanagiri","Baba Budangiri","Hirekolale Lake","Jhari Falls","Coffee Museum"],"best_months":[1,2,3,10,11,12],"budget_low":2500,"budget_high":7000,"visit_days":2,"accessibility":67,"popularity":84,"image":"https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?auto=format&fit=crop&w=1200&q=85","season_note":"October to March is a common trekking and sightseeing window; monsoon conditions can affect trails."},
    {"slug":"udupi","name":"Udupi","district":"Udupi","region":"Coastal Karnataka","lat":13.3409,"lon":74.7421,"category":"Coastal & Religious","tags":["beach","temple","food","family","coast"],"interests":["beaches","religious tourism","family sightseeing"],"description":"A coastal district known for Sri Krishna Matha, cuisine, beaches and nearby island and estuary landscapes.","attractions":["Sri Krishna Matha","Malpe Beach","St. Mary's Islands","Kaup Lighthouse","Mattu Beach"],"best_months":[1,2,3,10,11,12],"budget_low":2000,"budget_high":6000,"visit_days":2,"accessibility":80,"popularity":83,"image":"https://images.unsplash.com/photo-1501785888041-af3ef285b470?auto=format&fit=crop&w=1200&q=85","season_note":"Post-monsoon and winter months are generally more suitable for coastal visits and boat trips."},
    {"slug":"jog-falls","name":"Jog Falls","district":"Shivamogga","region":"Malnad","lat":14.2296,"lon":74.8068,"category":"Waterfall & Nature","tags":["waterfall","nature","viewpoint","photography"],"interests":["nature and hill stations","wildlife and forests","family sightseeing"],"description":"One of India's best-known waterfall destinations on the Sharavathi River, with views that vary significantly by season and water release.","attractions":["Jog Falls Viewpoints","Sharavathi Valley","Linganamakki Dam Viewpoints","Nearby forest trails"],"best_months":[7,8,9,10,11],"budget_low":1600,"budget_high":4200,"visit_days":1,"accessibility":60,"popularity":82,"image":"https://images.unsplash.com/photo-1432405972618-c60b0225b8f9?auto=format&fit=crop&w=1200&q=85","season_note":"Water flow is often strongest during and just after monsoon, but heavy rain can affect access and visibility."},
    {"slug":"kabini","name":"Kabini","district":"Mysuru","region":"Southern Karnataka","lat":11.9352,"lon":76.3285,"category":"Wildlife & Forest","tags":["wildlife","forest","safari","nature","photography"],"interests":["wildlife and forests","nature and hill stations"],"description":"A forest-and-river landscape associated with wildlife tourism, nature stays and guided safari experiences.","attractions":["Kabini Backwaters","Nagarahole National Park","Boat Safari (seasonal/operator dependent)","Nature Trails"],"best_months":[1,2,3,4,10,11,12],"budget_low":5000,"budget_high":14000,"visit_days":2,"accessibility":55,"popularity":80,"image":"https://images.unsplash.com/photo-1516026672322-bc52d61a55d5?auto=format&fit=crop&w=1200&q=85","season_note":"Safari availability, park rules and animal sightings vary; confirm permitted activities with official operators."},
    {"slug":"badami","name":"Badami","district":"Bagalkot","region":"North Karnataka","lat":15.9149,"lon":75.6768,"category":"Heritage & Archaeology","tags":["heritage","history","architecture","temple","rock-cut"],"interests":["historical and heritage tourism","religious tourism"],"description":"A historic town famous for rock-cut cave temples, red sandstone cliffs and early Chalukyan architecture.","attractions":["Badami Cave Temples","Agastya Lake","Bhutanatha Temples","Badami Fort","Pattadakal (nearby)"],"best_months":[1,2,10,11,12],"budget_low":1700,"budget_high":4800,"visit_days":1,"accessibility":64,"popularity":78,"image":"https://images.unsplash.com/photo-1561361513-2d000a50f0dc?auto=format&fit=crop&w=1200&q=85","season_note":"Cooler months make walking around the caves and monuments more comfortable."},
]

SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS users (
 id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE NOT NULL, full_name TEXT NOT NULL,
 password_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'tourist' CHECK(role IN ('tourist','admin')),
 origin TEXT DEFAULT '', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, last_login TEXT
);
CREATE TABLE IF NOT EXISTS destinations (
 id INTEGER PRIMARY KEY AUTOINCREMENT, slug TEXT UNIQUE NOT NULL, name TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'Karnataka',
 district TEXT, region TEXT, latitude REAL, longitude REAL, category TEXT, tags_json TEXT NOT NULL DEFAULT '[]',
 interests_json TEXT NOT NULL DEFAULT '[]', description TEXT, attractions_json TEXT NOT NULL DEFAULT '[]',
 best_months_json TEXT NOT NULL DEFAULT '[]', budget_low REAL, budget_high REAL, visit_days INTEGER,
 accessibility_score REAL, popularity_index REAL, capacity_per_month REAL, image_url TEXT, season_note TEXT,
 active INTEGER NOT NULL DEFAULT 1, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS seasonal_suitability (
 id INTEGER PRIMARY KEY AUTOINCREMENT, destination_id INTEGER NOT NULL REFERENCES destinations(id) ON DELETE CASCADE,
 month INTEGER NOT NULL CHECK(month BETWEEN 1 AND 12), score REAL NOT NULL CHECK(score BETWEEN 0 AND 100),
 label TEXT NOT NULL, basis TEXT NOT NULL DEFAULT 'Editorial seasonal guidance; not official visitor or weather statistics',
 UNIQUE(destination_id, month)
);
CREATE TABLE IF NOT EXISTS weather_records (
 id INTEGER PRIMARY KEY AUTOINCREMENT, destination_id INTEGER NOT NULL REFERENCES destinations(id) ON DELETE CASCADE,
 observed_at TEXT NOT NULL, record_type TEXT NOT NULL, temperature_c REAL, precipitation_mm REAL, humidity_pct REAL,
 wind_kmh REAL, weather_code INTEGER, source TEXT NOT NULL, payload_json TEXT, UNIQUE(destination_id, observed_at, record_type)
);
CREATE TABLE IF NOT EXISTS weather_cache (
 cache_key TEXT PRIMARY KEY, fetched_at TEXT NOT NULL, payload_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tourism_stats (
 id INTEGER PRIMARY KEY AUTOINCREMENT, destination_id INTEGER NOT NULL REFERENCES destinations(id), year INTEGER NOT NULL,
 month INTEGER NOT NULL CHECK(month BETWEEN 1 AND 12), visitors REAL NOT NULL CHECK(visitors>=0),
 source_id INTEGER, imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, notes TEXT,
 UNIQUE(destination_id, year, month)
);
CREATE TABLE IF NOT EXISTS reviews (
 id INTEGER PRIMARY KEY AUTOINCREMENT, destination_id INTEGER NOT NULL REFERENCES destinations(id), user_id INTEGER REFERENCES users(id),
 author TEXT NOT NULL, rating REAL CHECK(rating BETWEEN 1 AND 5), review_text TEXT NOT NULL,
 source TEXT NOT NULL DEFAULT 'User submitted feedback', review_date TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 sentiment TEXT, aspects_json TEXT NOT NULL DEFAULT '[]', image_url TEXT
);
CREATE TABLE IF NOT EXISTS recommendation_history (
 id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER REFERENCES users(id), input_json TEXT NOT NULL,
 results_json TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS itineraries (
 id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 title TEXT NOT NULL, origin TEXT NOT NULL, month INTEGER NOT NULL, days INTEGER NOT NULL,
 plan_json TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS data_sources (
 id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, category TEXT NOT NULL, url TEXT,
 status TEXT NOT NULL, attribution TEXT, reliability TEXT, last_updated TEXT, notes TEXT
);
CREATE TABLE IF NOT EXISTS data_quality_reports (
 id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 report_json TEXT NOT NULL, generated_by INTEGER REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS recommendation_weights (
 key TEXT PRIMARY KEY, value REAL NOT NULL, label TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS password_reset_tokens (
 id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 token_hash TEXT NOT NULL UNIQUE, expires_at TEXT NOT NULL, used_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_dest_state ON destinations(state, active);
CREATE INDEX IF NOT EXISTS idx_season_destination_month ON seasonal_suitability(destination_id, month);
CREATE INDEX IF NOT EXISTS idx_stats_destination_date ON tourism_stats(destination_id, year, month);
CREATE INDEX IF NOT EXISTS idx_reviews_destination ON reviews(destination_id);
CREATE INDEX IF NOT EXISTS idx_itineraries_user ON itineraries(user_id);
CREATE TABLE IF NOT EXISTS community_posts (
 id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 destination_slug TEXT REFERENCES destinations(slug), title TEXT NOT NULL, body TEXT NOT NULL,
 image_url TEXT, post_type TEXT NOT NULL DEFAULT 'story', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS travel_journal (
 id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 destination_slug TEXT REFERENCES destinations(slug), title TEXT NOT NULL, visit_date TEXT,
 notes TEXT NOT NULL, image_url TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS trip_groups (
 id INTEGER PRIMARY KEY AUTOINCREMENT, owner_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 itinerary_id INTEGER REFERENCES itineraries(id) ON DELETE SET NULL, name TEXT NOT NULL,
 invite_code TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS trip_group_members (
 group_id INTEGER NOT NULL REFERENCES trip_groups(id) ON DELETE CASCADE,
 user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 joined_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(group_id,user_id)
);
CREATE TABLE IF NOT EXISTS shared_itineraries (
 id INTEGER PRIMARY KEY AUTOINCREMENT, itinerary_id INTEGER NOT NULL REFERENCES itineraries(id) ON DELETE CASCADE,
 owner_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, share_token TEXT NOT NULL UNIQUE,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS trip_group_suggestions (
 id INTEGER PRIMARY KEY AUTOINCREMENT, group_id INTEGER NOT NULL REFERENCES trip_groups(id) ON DELETE CASCADE,
 user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, destination_slug TEXT NOT NULL REFERENCES destinations(slug),
 note TEXT DEFAULT '', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS trip_group_votes (
 suggestion_id INTEGER NOT NULL REFERENCES trip_group_suggestions(id) ON DELETE CASCADE,
 user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(suggestion_id,user_id)
);
CREATE TABLE IF NOT EXISTS destination_checkins (
 id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 destination_slug TEXT NOT NULL REFERENCES destinations(slug), visited_on TEXT NOT NULL DEFAULT CURRENT_DATE,
 note TEXT DEFAULT '', UNIQUE(user_id,destination_slug,visited_on)
);
CREATE INDEX IF NOT EXISTS idx_community_created ON community_posts(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_journal_user ON travel_journal(user_id,created_at DESC);
"""


class ClosingConnection(sqlite3.Connection):
    """Connection context manager that also closes the handle on exit."""
    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=30, factory=ClosingConnection)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _season_score(dest: dict[str, Any], month: int) -> tuple[float, str]:
    preferred = set(dest["best_months"])
    if month in preferred:
        return 92.0, "Usually preferred window"
    # Transition shoulder months remain reasonable for several categories.
    next_month = 1 if month == 12 else month + 1
    previous_month = 12 if month == 1 else month - 1
    if next_month in preferred or previous_month in preferred:
        return 68.0, "Shoulder season"
    if dest["slug"] == "jog-falls" and month in (6, 7):
        return 78.0, "Waterfall flow may be strong; check rainfall and access"
    if dest["category"] in ("Beach & Coastal", "Coastal & Religious") and month in (6, 7, 8, 9):
        return 28.0, "Southwest monsoon can limit beach activities"
    if dest["category"] in ("Hill Station & Nature",) and month in (6, 7, 8, 9):
        return 48.0, "Rain can affect trails and road access"
    if dest["slug"] in ("hampi", "badami") and month in (4, 5):
        return 32.0, "Hot conditions can make outdoor sightseeing uncomfortable"
    return 52.0, "Mixed seasonal conditions; check current conditions"


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)
        review_columns={r[1] for r in conn.execute("PRAGMA table_info(reviews)").fetchall()}
        if "image_url" not in review_columns:
            conn.execute("ALTER TABLE reviews ADD COLUMN image_url TEXT")
        for d in DESTINATIONS:
            # Seed the reference catalogue only once. Do not overwrite administrator edits
            # (budget, popularity, accessibility, description, image, etc.) at every restart.
            conn.execute("""INSERT OR IGNORE INTO destinations
                (slug,name,state,district,region,latitude,longitude,category,tags_json,interests_json,description,
                 attractions_json,best_months_json,budget_low,budget_high,visit_days,accessibility_score,popularity_index,image_url,season_note)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (d["slug"],d["name"],"Karnataka",d["district"],d["region"],d["lat"],d["lon"],d["category"],
                 json.dumps(d["tags"]),json.dumps(d["interests"]),d["description"],json.dumps(d["attractions"]),
                 json.dumps(d["best_months"]),d["budget_low"],d["budget_high"],d["visit_days"],d["accessibility"],
                 d["popularity"],d["image"],d["season_note"]))
            dest_id = conn.execute("SELECT id FROM destinations WHERE slug=?", (d["slug"],)).fetchone()["id"]
            for month in range(1, 13):
                score, label = _season_score(d, month)
                conn.execute("""INSERT INTO seasonal_suitability(destination_id,month,score,label)
                    VALUES(?,?,?,?) ON CONFLICT(destination_id,month) DO NOTHING""",
                    (dest_id, month, score, label))
        sources = [
            ("Open-Meteo Weather API","Weather","https://open-meteo.com/","Available on demand","Open-Meteo; see terms and attribution","Modelled weather data; not an official station observation feed",None,"Live integration is attempted by the app; results are cached."),
            ("OpenStreetMap","Geospatial","https://www.openstreetmap.org/","Map tiles configured","© OpenStreetMap contributors","Community-maintained map data",None,"Tiles are loaded on demand from OSM; follow tile usage policy."),
            ("India Tourism Data Portal","Official tourism statistics","https://data.tourism.gov.in/","Manual import required","Ministry of Tourism, Government of India","Official government source; verify dataset-level metadata",None,"Download Karnataka/state or destination series and import the supported CSV format."),
            ("Open Government Data Platform India","Official open data","https://data.gov.in/","Manual dataset download required","Government of India Open Government Data Platform","Check the individual publisher, licence and update metadata",None,"Use published downloadable datasets and import supported CSV extracts; no direct API resource is preconfigured."),
            ("Karnataka Tourism","Destination reference","https://karnatakatourism.org/","Reference link; not connected as API","Department of Tourism, Government of Karnataka","Official destination information; verify page-level claims",None,"Use official pages for verification; no automated scraper is enabled."),
            ("TourInsight visitor feedback","Reviews","","User submissions enabled","User-submitted feedback","Unverified user-generated content",None,"Reviews are user-submitted and are not presented as official survey data."),
            ("Karnataka destination baseline","Destination metadata","","Local reference catalogue","TourInsight editorial metadata","Indicative editorial reference; not official statistics",None,"Budget, access and popularity baselines are planning estimates, not official counts."),
        ]
        for s in sources:
            conn.execute("INSERT OR IGNORE INTO data_sources(name,category,url,status,attribution,reliability,last_updated,notes) VALUES(?,?,?,?,?,?,?,?)", s)
        defaults = [
            ("seasonal",25.0,"Seasonal suitability"),("weather",20.0,"Weather suitability"),
            ("interest",20.0,"Interest match"),("popularity",15.0,"Destination popularity baseline"),
            ("budget",10.0,"Budget suitability"),("accessibility",10.0,"Accessibility"),
        ]
        for w in defaults:
            conn.execute("INSERT OR IGNORE INTO recommendation_weights(key,value,label) VALUES(?,?,?)", w)
        conn.commit()


def row_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def destination_dict(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    for field, target in (("tags_json","tags"),("interests_json","interests"),("attractions_json","attractions"),("best_months_json","best_months")):
        d[target] = json.loads(d.pop(field) or "[]")
    return d
