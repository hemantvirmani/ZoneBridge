"""
Strava OAuth 2.0 and activity upload helpers.

Token storage: ~/.strava_tokens.json (auto-refreshed on expiry)
"""
from __future__ import annotations

import json
import time
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import requests

TOKEN_FILE = Path.home() / ".strava_tokens.json"
AUTH_URL = "https://www.strava.com/oauth/authorize"
TOKEN_URL = "https://www.strava.com/oauth/token"
API_BASE = "https://www.strava.com/api/v3"


def _save(tokens: dict) -> None:
    TOKEN_FILE.write_text(json.dumps(tokens, indent=2))


def _load() -> dict | None:
    return json.loads(TOKEN_FILE.read_text()) if TOKEN_FILE.exists() else None


def _refresh(client_id: str, client_secret: str, refresh_token: str) -> dict:
    resp = requests.post(
        TOKEN_URL,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        timeout=30,
    )
    resp.raise_for_status()
    tokens = resp.json()
    _save(tokens)
    return tokens


def get_valid_token(client_id: str, client_secret: str) -> str | None:
    tokens = _load()
    if not tokens:
        return None
    expires_at = tokens.get("expires_at", 0)
    # Refresh 5 minutes early
    if time.time() >= (expires_at - 300):
        print("Strava access token expiring -- refreshing...")
        tokens = _refresh(client_id, client_secret, tokens["refresh_token"])
    return tokens["access_token"]


class _Handler(BaseHTTPRequestHandler):
    auth_code: str | None = None
    error: str | None = None

    def do_GET(self):
        params = parse_qs(urlparse(self.path).query)
        if "code" in params:
            _Handler.auth_code = params["code"][0]
            body = b"<html><body><h1>Authorization successful!</h1><p>You may close this tab.</p></body></html>"
            status = 200
        else:
            _Handler.error = params.get("error", ["unknown"])[0]
            body = b"<html><body><h1>Authorization failed.</h1><p>Check your terminal.</p></body></html>"
            status = 400
        self.send_response(status)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):
        pass


def _start_server(host: str, port: int) -> HTTPServer:
    _Handler.auth_code = None
    _Handler.error = None
    server = HTTPServer((host, port), _Handler)
    return server


def authorize(
    client_id: str,
    client_secret: str,
    redirect_uri: str = "http://localhost:8080",
    scope: str = "activity:write,activity:read_all",
) -> str:
    parsed = urlparse(redirect_uri)
    host = parsed.hostname or "localhost"
    port = parsed.port or 80

    params = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "approval_prompt": "auto",
        "scope": scope,
    }
    auth_url = f"{AUTH_URL}?{urlencode(params)}"

    server = _start_server(host, port)

    print("\nOpening your browser for Strava authorization...")
    print(f"If the browser doesn't open automatically, visit:\n  {auth_url}\n")
    webbrowser.open(auth_url)

    server.timeout = 1
    deadline = time.time() + 180
    print("Waiting for Strava callback (up to 3 minutes)...")
    while not _Handler.auth_code and not _Handler.error:
        server.handle_request()
        if time.time() > deadline:
            raise RuntimeError("Timed out waiting for Strava authorization callback.")

    if _Handler.error:
        raise RuntimeError(f"Strava returned an error: {_Handler.error}")
    if not _Handler.auth_code:
        raise RuntimeError("No authorization code received from Strava.")

    resp = requests.post(
        TOKEN_URL,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": _Handler.auth_code,
            "grant_type": "authorization_code",
        },
        timeout=30,
    )
    resp.raise_for_status()
    tokens = resp.json()
    _save(tokens)

    print(f"Authorization successful! Tokens saved -> {TOKEN_FILE}")
    return tokens["access_token"]


class StravaClient:
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str = "http://localhost:8080"):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri

    def _token(self) -> str:
        token = get_valid_token(self.client_id, self.client_secret)
        if token is None:
            print("No stored Strava token -- starting authorization flow...")
            token = authorize(self.client_id, self.client_secret, self.redirect_uri)
        return token

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._token()}"}

    def create_activity(self, payload: dict) -> dict:
        url = f"{API_BASE}/activities"
        resp = requests.post(url, headers=self._headers(), data=payload, timeout=30)
        if resp.status_code == 429:
            reset_secs = int(resp.headers.get("RateLimit-Reset", 60))
            print(f"  Rate limit hit -- waiting {reset_secs}s...")
            time.sleep(reset_secs + 1)
            resp = requests.post(url, headers=self._headers(), data=payload, timeout=30)
        resp.raise_for_status()
        return resp.json()

