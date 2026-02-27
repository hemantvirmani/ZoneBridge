"""
Fitbit Web API client.
Fetches intraday heart rate data (1-min resolution) day by day.
Responses are cached in .cache/ to stay well under the 150 req/hr limit.
"""
import json
import time
from datetime import date, timedelta
from pathlib import Path

import requests

from auth import get_valid_token, authorize

API_BASE = "https://api.fitbit.com"
CACHE_DIR = Path(".cache")


def _ensure_cache():
    CACHE_DIR.mkdir(exist_ok=True)


def _cache_path(date_str: str) -> Path:
    return CACHE_DIR / f"hr_{date_str}.json"


def _load_cache(date_str: str):
    p = _cache_path(date_str)
    if p.exists():
        return json.loads(p.read_text())
    return None


def _save_cache(date_str: str, data):
    _ensure_cache()
    _cache_path(date_str).write_text(json.dumps(data))


class FitbitClient:
    def __init__(self, client_id: str, client_secret: str = "", redirect_uri: str = "https://192.168.86.39:8080"):
        self.client_id     = client_id
        self.client_secret = client_secret
        self.redirect_uri  = redirect_uri

    # ------------------------------------------------------------------
    # Auth helpers
    # ------------------------------------------------------------------

    def _token(self) -> str:
        token = get_valid_token(self.client_id, self.client_secret)
        if token is None:
            print("No stored token — starting authorization flow…")
            token = authorize(self.client_id, self.client_secret, self.redirect_uri)
        return token

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._token()}"}

    # ------------------------------------------------------------------
    # Intraday heart rate (single day, 1-min resolution)
    # ------------------------------------------------------------------

    def get_intraday_hr(self, date_str: str, use_cache: bool = True) -> list[dict]:
        """
        Return a list of {'time': 'HH:MM:SS', 'value': bpm} dicts for *date_str*.
        Results are cached to .cache/hr_<date>.json.
        """
        # Don't cache today — data may still be coming in
        today = date.today().isoformat()
        can_cache = use_cache and date_str != today

        if can_cache:
            cached = _load_cache(date_str)
            if cached is not None:
                return cached

        url = (
            f"{API_BASE}/1/user/-/activities/heart"
            f"/date/{date_str}/1d/1min.json"
        )
        resp = requests.get(url, headers=self._headers(), timeout=30)

        if resp.status_code == 429:
            reset_secs = int(resp.headers.get("Fitbit-Rate-Limit-Reset", 60))
            print(f"  Rate limit hit — waiting {reset_secs}s…")
            time.sleep(reset_secs + 1)
            resp = requests.get(url, headers=self._headers(), timeout=30)

        resp.raise_for_status()
        body = resp.json()
        intraday = body.get("activities-heart-intraday", {})
        dataset = intraday.get("dataset", [])
        if not dataset:
            print(f"    ⚠  No intraday data returned. Raw keys: {list(body.keys())}, intraday keys: {list(intraday.keys())}")

        if can_cache:
            _save_cache(date_str, dataset)

        return dataset

    # ------------------------------------------------------------------
    # Fetch a date range (day by day, with progress output)
    # ------------------------------------------------------------------

    def get_hr_range(
        self,
        start: date,
        end: date,
        use_cache: bool = True,
    ) -> dict[str, list[dict]]:
        """
        Fetch intraday HR for every day in [start, end].
        Returns {date_str: [dataset]} mapping.
        """
        result: dict[str, list[dict]] = {}
        current = start
        total = (end - start).days + 1
        i = 0

        while current <= end:
            i += 1
            date_str = current.isoformat()
            cached = _load_cache(date_str) if use_cache and date_str != date.today().isoformat() else None

            if cached is not None:
                print(f"  [{i}/{total}] {date_str} (cached)")
                result[date_str] = cached
            else:
                print(f"  [{i}/{total}] {date_str} — fetching from API…")
                try:
                    result[date_str] = self.get_intraday_hr(date_str, use_cache=use_cache)
                except requests.HTTPError as exc:
                    print(f"    Warning: {exc}")
                    result[date_str] = []

            current += timedelta(days=1)

        return result
