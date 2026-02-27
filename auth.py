"""
Fitbit OAuth 2.0  –  Authorization Code + PKCE + Client Secret
================================================================
Supports redirect URIs of the form  https://<local-ip>:<port>
by spawning a temporary HTTPS server with a self-signed certificate.

Token storage: ~/.fitbit_tokens.json  (auto-refreshed on expiry)
"""
from __future__ import annotations

import base64
import hashlib
import ipaddress
import json
import secrets
import ssl
import tempfile
import time
import webbrowser
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import requests

TOKEN_FILE = Path.home() / ".fitbit_tokens.json"
AUTH_URL   = "https://www.fitbit.com/oauth2/authorize"
TOKEN_URL  = "https://api.fitbit.com/oauth2/token"
SCOPES     = "heartrate activity profile"


# ---------------------------------------------------------------------------
# PKCE
# ---------------------------------------------------------------------------

def _pkce() -> tuple[str, str]:
    verifier  = secrets.token_urlsafe(96)[:128]
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b"=").decode()
    return verifier, challenge


# ---------------------------------------------------------------------------
# Token persistence & refresh
# ---------------------------------------------------------------------------

def _save(tokens: dict) -> None:
    TOKEN_FILE.write_text(json.dumps(tokens, indent=2))


def _load() -> dict | None:
    return json.loads(TOKEN_FILE.read_text()) if TOKEN_FILE.exists() else None


def _basic_auth(client_id: str, client_secret: str) -> str:
    raw = f"{client_id}:{client_secret}".encode()
    return "Basic " + base64.b64encode(raw).decode()


def _refresh(client_id: str, client_secret: str, refresh_token: str) -> dict:
    headers = {"Authorization": _basic_auth(client_id, client_secret)} if client_secret else {}
    resp = requests.post(
        TOKEN_URL,
        headers=headers,
        data={
            "client_id":     client_id,
            "grant_type":    "refresh_token",
            "refresh_token": refresh_token,
        },
        timeout=30,
    )
    resp.raise_for_status()
    tokens = resp.json()
    tokens["obtained_at"] = datetime.now(timezone.utc).isoformat()
    _save(tokens)
    return tokens


def get_valid_token(client_id: str, client_secret: str = "") -> str | None:
    """Return a valid access token, refreshing if needed. None if not yet authorized."""
    tokens = _load()
    if not tokens:
        return None
    obtained = datetime.fromisoformat(tokens.get("obtained_at", "2000-01-01T00:00:00+00:00"))
    if obtained.tzinfo is None:
        obtained = obtained.replace(tzinfo=timezone.utc)
    expires_in = tokens.get("expires_in", 28800)
    if datetime.now(timezone.utc) >= obtained + timedelta(seconds=expires_in - 300):
        print("Access token expiring — refreshing…")
        tokens = _refresh(client_id, client_secret, tokens["refresh_token"])
    return tokens["access_token"]


# ---------------------------------------------------------------------------
# Self-signed TLS certificate (needed for https:// redirect URIs)
# ---------------------------------------------------------------------------

def _make_self_signed_cert(ip: str) -> tuple[Path, Path]:
    """Generate a temporary self-signed cert/key pair for *ip*."""
    try:
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID
    except ImportError:
        raise SystemExit(
            "The 'cryptography' package is required for HTTPS redirect URIs.\n"
            "Install it:  pip install cryptography"
        )

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, ip)])
    now  = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + timedelta(days=1))
        .add_extension(
            x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address(ip))]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )

    tmp_dir  = Path(tempfile.mkdtemp())
    cert_pem = tmp_dir / "cert.pem"
    key_pem  = tmp_dir / "key.pem"
    cert_pem.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_pem.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )
    return cert_pem, key_pem


# ---------------------------------------------------------------------------
# Local callback server
# ---------------------------------------------------------------------------

class _Handler(BaseHTTPRequestHandler):
    auth_code: str | None = None
    error:     str | None = None

    def do_GET(self):
        params = parse_qs(urlparse(self.path).query)
        if "code" in params:
            _Handler.auth_code = params["code"][0]
            body  = b"<html><body><h1>Authorization successful!</h1><p>You may close this tab.</p></body></html>"
            status = 200
        else:
            _Handler.error = params.get("error", ["unknown"])[0]
            body  = b"<html><body><h1>Authorization failed.</h1><p>Check your terminal.</p></body></html>"
            status = 400
        self.send_response(status)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):  # silence request logs
        pass


def _start_server(host: str, port: int, use_ssl: bool) -> HTTPServer:
    _Handler.auth_code = None
    _Handler.error     = None
    server = HTTPServer((host, port), _Handler)

    if use_ssl:
        cert_pem, key_pem = _make_self_signed_cert(host)
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(str(cert_pem), str(key_pem))
        server.socket = ctx.wrap_socket(server.socket, server_side=True)
        print(f"  (HTTPS server started on {host}:{port} with self-signed cert)")

    return server


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def authorize(
    client_id:     str,
    client_secret: str = "",
    redirect_uri:  str = "https://192.168.86.39:8080",
) -> str:
    """
    Full OAuth 2.0 + PKCE + (optional) client-secret authorization flow.
    Opens a browser, waits for Fitbit to redirect back, exchanges the code,
    persists the tokens, and returns the access token.
    """
    verifier, challenge = _pkce()

    parsed   = urlparse(redirect_uri)
    use_ssl  = parsed.scheme == "https"
    host     = parsed.hostname or "localhost"
    port     = parsed.port or (443 if use_ssl else 80)

    params = {
        "client_id":             client_id,
        "response_type":         "code",
        "code_challenge":        challenge,
        "code_challenge_method": "S256",
        "scope":                 SCOPES,
        "redirect_uri":          redirect_uri,
    }
    auth_url = f"{AUTH_URL}?{urlencode(params)}"

    server = _start_server(host, port, use_ssl)

    print("\nOpening your browser for Fitbit authorization…")
    if use_ssl:
        print("  ⚠  Your browser will warn about a self-signed certificate.")
        print("     Click 'Advanced' → 'Proceed to <IP>' to continue.\n")
    print(f"If the browser doesn't open automatically, visit:\n  {auth_url}\n")
    webbrowser.open(auth_url)

    # Loop until the auth code (or an error) arrives.
    # handle_request() only processes one connection at a time; with a
    # self-signed cert the browser may make several connections (SSL probe,
    # favicon, …) before the real redirect lands.
    server.timeout = 1  # seconds per poll
    deadline = time.time() + 180  # 3-minute overall timeout
    print("Waiting for Fitbit callback (up to 3 minutes)…")
    while not _Handler.auth_code and not _Handler.error:
        server.handle_request()
        if time.time() > deadline:
            raise RuntimeError(
                "Timed out waiting for Fitbit authorization callback."
            )

    if _Handler.error:
        raise RuntimeError(f"Fitbit returned an error: {_Handler.error}")
    if not _Handler.auth_code:
        raise RuntimeError("No authorization code received from Fitbit.")

    # ── Exchange code for tokens ──────────────────────────────────────
    headers = {"Authorization": _basic_auth(client_id, client_secret)} if client_secret else {}
    resp = requests.post(
        TOKEN_URL,
        headers=headers,
        data={
            "client_id":    client_id,
            "grant_type":   "authorization_code",
            "code":         _Handler.auth_code,
            "code_verifier": verifier,
            "redirect_uri": redirect_uri,
        },
        timeout=30,
    )
    resp.raise_for_status()
    tokens = resp.json()
    tokens["obtained_at"] = datetime.now(timezone.utc).isoformat()
    _save(tokens)

    print(f"Authorization successful!  Tokens saved → {TOKEN_FILE}")
    return tokens["access_token"]
