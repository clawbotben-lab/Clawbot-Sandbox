from datetime import date, timedelta
from typing import Dict

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from dashgo_client import DashGoClient, normalize_points

app = FastAPI(title="DashGo Overlay")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


def align_series(streams, creations, days: int):
    end = date.today()
    start = end - timedelta(days=max(1, days - 1))
    dates = [(start + timedelta(days=i)).isoformat() for i in range(days)]

    s_map = {x["date"]: x["value"] for x in streams}
    c_map = {x["date"]: x["value"] for x in creations}

    return {
        "labels": dates,
        "spotify_streams": [s_map.get(d, 0) for d in dates],
        "tiktok_creations": [c_map.get(d, 0) for d in dates],
    }


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/overlay")
def overlay(isrc: str = Query(..., min_length=8), days: int = Query(14, ge=1, le=90)):
    client = DashGoClient()
    if not client.token:
        raise HTTPException(status_code=400, detail="Missing DASHGO_TOKEN in environment")

    try:
        track_id = client.resolve_track_id_by_isrc(isrc)
        if not track_id:
            raise HTTPException(status_code=404, detail=f"Track not found for ISRC: {isrc}")

        spotify_raw = client.fetch_sales_trends("spotify", track_id, days)
        tiktok_raw = client.fetch_sales_trends("tiktok", track_id, days)

        spotify_points = normalize_points(spotify_raw)
        tiktok_points = normalize_points(tiktok_raw)

        aligned = align_series(spotify_points, tiktok_points, days)
        return JSONResponse(
            {
                "isrc": isrc,
                "track_id": track_id,
                "days": days,
                **aligned,
                "raw": {
                    "spotify_count": len(spotify_points),
                    "tiktok_count": len(tiktok_points),
                },
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
