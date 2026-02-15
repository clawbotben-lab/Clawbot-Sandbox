import os
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

import httpx
from dotenv import load_dotenv

load_dotenv()


class DashGoClient:
    def __init__(self):
        self.base_url = os.getenv("DASHGO_BASE_URL", "https://api.dashgo.com/api/v2").rstrip("/")
        self.token = os.getenv("DASHGO_TOKEN", "")
        self.auth_header = os.getenv("DASHGO_AUTH_HEADER", "Authorization")
        self.auth_scheme = os.getenv("DASHGO_AUTH_SCHEME", "Bearer")

    def _headers(self) -> Dict[str, str]:
        if not self.token:
            return {}
        token_value = f"{self.auth_scheme} {self.token}".strip() if self.auth_scheme else self.token
        return {self.auth_header: token_value, "Accept": "application/json"}

    def _get(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        with httpx.Client(timeout=30) as client:
            resp = client.get(url, headers=self._headers(), params=params)
            resp.raise_for_status()
            return resp.json() if resp.content else {}

    def resolve_track_id_by_isrc(self, isrc: str) -> Optional[str]:
        payload = self._get("/tracks/", {"isrc": isrc})
        for key in ["data", "results", "items", "tracks"]:
            if isinstance(payload.get(key), list) and payload[key]:
                first = payload[key][0]
                if isinstance(first, dict):
                    for id_key in ["id", "track_id"]:
                        if first.get(id_key) is not None:
                            return str(first[id_key])
        if isinstance(payload, list) and payload:
            first = payload[0]
            if isinstance(first, dict):
                return str(first.get("id") or first.get("track_id"))
        if isinstance(payload.get("id"), (int, str)):
            return str(payload["id"])
        return None

    def fetch_sales_trends(self, dsp: str, track_id: str, days: int = 14) -> Dict[str, Any]:
        date_to = date.today()
        date_from = date_to - timedelta(days=max(1, days - 1))
        params = {
            "dsp": dsp,
            "unit_type": "track",
            "unit_id": track_id,
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
        }
        return self._get("/sales_trends", params)


def normalize_points(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    candidates = []
    for key in ["data", "results", "items", "rows", "trends"]:
        val = payload.get(key)
        if isinstance(val, list):
            candidates = val
            break
    if not candidates and isinstance(payload, list):
        candidates = payload

    out = []
    for row in candidates:
        if not isinstance(row, dict):
            continue
        day = row.get("date") or row.get("day") or row.get("report_date") or row.get("dt")
        value = None
        for vkey in ["value", "count", "streams", "creations", "total", "qty"]:
            if row.get(vkey) is not None:
                value = row.get(vkey)
                break
        if day is None or value is None:
            continue
        try:
            v = float(value)
        except Exception:
            continue
        out.append({"date": str(day), "value": v})

    out.sort(key=lambda x: x["date"])
    return out
