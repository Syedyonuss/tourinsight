# TourInsight 3.5

TourInsight is a Karnataka tourism discovery, trip-planning, community and tourism-intelligence web application.

## Architecture

- Frontend: HTML, CSS and JavaScript in `web/`, deployed on Vercel.
- Backend: FastAPI in `backend/`, deployed on Render.
- Persistence: SQLite and uploaded files on Render's persistent disk.

The browser calls the backend through same-origin Vercel rewrites for `/api/*`, `/uploads/*` and `/shared/*`.

## Deploy from Windows

1. Deploy the backend first using Render Blueprint (New → Blueprint, select this repository). Review Starter web-service and persistent-disk costs before applying.
2. Copy the Render service origin, e.g. `https://tourinsight-api-xxxx.onrender.com`.
3. Replace all three `REPLACE-WITH-YOUR-RENDER-SERVICE` values in `vercel.json` with the actual Render host, then commit and push.
4. In this repository's root folder, run `npm i -g vercel`, `vercel login`, then `vercel --prod`.
5. Set Framework Preset to **Other**, project root to the repository root, and Output Directory to `web`.

Or import the repository through the Vercel dashboard with the same settings.

## Run locally

Requires Python 3.10+.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn backend.main:APP --reload --port 8000
```

Open http://127.0.0.1:8000.

## Important notes

A Vercel static deployment alone does not host the FastAPI backend. Render is required for login, saved trips, analytics and other API-backed features. The included Render Blueprint uses a paid Starter service and persistent disk so SQLite data and uploads survive restarts; review current pricing before applying.

Do not commit `.env`, passwords, API keys, local databases or real user uploads.

Live hotel inventory, verified bookings and live Reddit ingestion require separate provider integrations; deployment does not create those integrations.
