# DashGo Streams vs TikTok Overlay App

Small web app that overlays daily Spotify streams and TikTok creations for a provided ISRC over the last N days (default 14).

## Setup

```bash
cd apps/dashgo_overlay
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# fill in DASHGO_TOKEN (and adjust headers if needed)
uvicorn app:app --reload --port 8787
```

Open: http://localhost:8787

## Deploy on Render

### Option 1: Blueprint (recommended)
1. Push this repo to GitHub.
2. In Render: **New +** → **Blueprint**.
3. Select the repo and deploy `apps/dashgo_overlay/render.yaml`.
4. Set `DASHGO_TOKEN` in Render environment variables.

### Option 2: Manual Web Service
- **Root Directory:** `apps/dashgo_overlay`
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `uvicorn app:app --host 0.0.0.0 --port $PORT`
- Set env vars:
  - `DASHGO_BASE_URL=https://api.dashgo.com/api/v2`
  - `DASHGO_AUTH_HEADER=Authorization`
  - `DASHGO_AUTH_SCHEME=Bearer`
  - `DASHGO_TOKEN=...`

## Environment

- `DASHGO_BASE_URL` (default: `https://api.dashgo.com/api/v2`)
- `DASHGO_TOKEN` (required)
- `DASHGO_AUTH_SCHEME` (default: `Bearer`)
- `DASHGO_AUTH_HEADER` (default: `Authorization`)

Examples:
- Authorization Bearer token:
  - `DASHGO_AUTH_HEADER=Authorization`
  - `DASHGO_AUTH_SCHEME=Bearer`
- Custom header token (no scheme):
  - `DASHGO_AUTH_HEADER=X-API-KEY`
  - `DASHGO_AUTH_SCHEME=`

## Notes

Because DashGo response payloads can vary by endpoint/account, parser logic is defensive and attempts to normalize common date/value shapes.
