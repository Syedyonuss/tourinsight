# TourInsight 3.0 — Karnataka Tourism Discovery & Intelligence

TourInsight is a local-first tourism discovery, trip-planning and tourism analytics web application. The initial catalogue focuses on Karnataka and is designed so the destination database can expand to other Indian states.

## Run on Windows

1. Install Python 3.10 or newer. During installation, enable **Add Python to PATH**.
2. Extract the complete ZIP into a normal folder (not inside the ZIP preview).
3. Double-click `run_windows.bat`.
4. The launcher creates `.venv`, installs packages, initializes SQLite and starts the FastAPI server.
5. Open the exact `http://127.0.0.1:<port>` address printed in the terminal. Keep the terminal open while using TourInsight.

First launch requires an internet connection for Python package installation. Map tiles, fonts, weather and external provider links also require internet access.

## Run manually

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.main:APP --host 127.0.0.1 --port 8501
```

Open `http://127.0.0.1:8501`. API documentation is available at `/docs`.

## What's included

### Tourism discovery and planning
- Editorial neo-brutalist design system: warm cream, sage, moss, butter yellow and dusty peach; bold ink borders, offset shadows, responsive cards and reduced-motion-aware transitions.
- Karnataka destination explorer, search, category/region filters, saved places, comparison and interactive Leaflet map pins.
- SmartSeason transparent weighted destination recommendations and alternative destination discovery.
- Multi-stop itinerary generation, route visualization, saved itineraries, print/PDF and public read-only share links.
- Budget estimator, month-wise seasonal finder and packing checklist.

### Community and personal travel tools
- District-wise destination explorer based on the districts represented in the current destination catalogue. The map uses destination pins; it does not draw unverified district boundaries.
- Public local community posts: travel stories, tips, questions and photo stories.
- Optional JPG/PNG/WEBP photo uploads (maximum 5 MB) for community posts and visitor reviews. Files are stored in `web/uploads`.
- Collaborative trip groups with invite codes, optional saved-itinerary association, shared destination shortlists and member voting. Members join using their TourInsight account.
- Personal travel journal with dated notes and optional image URL.
- Travel passport check-ins and milestone challenges. Check-ins are self-reported, not GPS-verified.
- Transport shortcuts to KSRTC, IRCTC, Air India and OpenStreetMap directions. These are external links, not live timetable or fare integrations.
- Emergency reference: India emergency number 112, linked to the official portal. Confirm destination-specific local contacts independently.
- Basic English/Kannada/Hindi navigation-label switching. Destination descriptions and all content are not fully translated.
- Nearby destination suggestions calculated from the coordinates in the local catalogue.

### Tourism intelligence
- Tourism analytics, visitor sentiment, popularity forecasting, pressure/opportunity indicators and data quality checks.
- Admin tools for destination catalogue, source metadata, visitor-statistics imports, review imports and recommendation weights.
- SQLite persistence, session-backed authentication, role checks and API validation.

## Important data and integration notes

- The initial ten-destination Karnataka catalogue contains curated reference metadata. Cost, popularity and accessibility fields are planning baselines, not official statistics or live prices.
- Tourism popularity forecasting requires sufficient imported historical monthly visitor observations; it does not invent forecasts when records are insufficient.
- Sentiment analysis is an explainable English keyword/aspect baseline, not a trained domain-specific model.
- Weather is fetched on demand from Open-Meteo when available. Forecast availability depends on forecast horizon; historical climate and forecasts are distinguished in the interface.
- Map tiles are supplied by external map providers. OpenStreetMap/CARTO attribution is shown in the application.
- Community posts, journals, groups, check-ins and saved itineraries persist in the local SQLite database. A local installation is not automatically a public internet community: separate installations have separate databases unless deployed with a shared server/database.
- Uploaded community images are served from the local `web/uploads` folder. Back up this folder along with the database.
- Shared itinerary links are accessible to anyone who has the link. Do not include sensitive personal details in a shared plan.
- Transport links open external provider sites. Live seats, schedules, fares and booking are not queried.
- 112 is a pan-India emergency response number. TourInsight does not guarantee local rescue, hospital or police contact data for each attraction.

## Preserve your data during upgrades

Back up `database/tourinsight.db` and `web/uploads/` before replacing project files. New database tables and the optional review-photo column are created/migrated at startup. Do not overwrite your existing database with a fresh starter database if you want to retain accounts and saved content.

## Tests

Run:

```bash
python tests/smoke_test.py
```

The smoke suite currently checks 34 workflows covering the API, authentication, recommendations, itinerary storage/sharing, community posts, journal, check-ins, group boards and voting, transport shortcuts, emergency reference, analytics and admin workflows.


## 3.1 visual experience update
The overview now includes a service directory linking to the existing discovery, SmartSeason, trip planning, budget and packing tools, community, journal, passport, transport, and tourism-intelligence modules. The interface adds a bold forest/leaf/butter/coral/sky palette, scroll-direction-aware navigation, reversible scroll reveals, page transitions, reading progress and a back-to-top control. Motion automatically reduces when the operating system requests reduced motion.
