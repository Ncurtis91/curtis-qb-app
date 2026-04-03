"""
auth_qbo.py — QuickBooks Online OAuth 2.0 handler (plain requests)

Handles:
- Initial authorization (opens browser, catches callback on localhost:8080)
- Saving/loading tokens to tokens/qbo_token.json
- Auto-refreshing expired access tokens using the refresh token
"""
import base64
import json
import os
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlencode, parse_qs, urlparse

import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN_FILE = Path(__file__).parent / "tokens" / "qbo_token.json"

AUTH_URL    = "https://appcenter.intuit.com/connect/oauth2"
TOKEN_URL   = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
SCOPES      = "com.intuit.quickbooks.accounting"


def _client_id()     -> str: return os.getenv("QBO_CLIENT_ID", "")
def _client_secret() -> str: return os.getenv("QBO_CLIENT_SECRET", "")
def _redirect_uri()  -> str: return os.getenv("QBO_REDIRECT_URI", "http://localhost:8080/callback")
def _environment()   -> str: return os.getenv("QBO_ENVIRONMENT", "sandbox")
def _realm_id()      -> str: return os.getenv("QBO_REALM_ID", "")


def _basic_auth_header() -> str:
    encoded = base64.b64encode(f"{_client_id()}:{_client_secret()}".encode()).decode()
    return f"Basic {encoded}"


def _save_tokens(access_token: str, refresh_token: str, realm_id: str) -> None:
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(json.dumps({
        "access_token": access_token,
        "refresh_token": refresh_token,
        "realm_id": realm_id,
    }, indent=2))


def _load_tokens() -> dict | None:
    if TOKEN_FILE.exists():
        return json.loads(TOKEN_FILE.read_text())
    return None


def _exchange_code(auth_code: str, realm_id: str) -> dict:
    resp = requests.post(TOKEN_URL, headers={
        "Authorization": _basic_auth_header(),
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
    }, data={
        "grant_type": "authorization_code",
        "code": auth_code,
        "redirect_uri": _redirect_uri(),
    })
    resp.raise_for_status()
    return resp.json()


def _refresh_tokens(refresh_token: str) -> dict:
    resp = requests.post(TOKEN_URL, headers={
        "Authorization": _basic_auth_header(),
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
    }, data={
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    })
    resp.raise_for_status()
    return resp.json()


def _run_oauth_flow() -> dict:
    """Open browser, catch callback, exchange code for tokens."""
    params = {
        "client_id": _client_id(),
        "response_type": "code",
        "scope": SCOPES,
        "redirect_uri": _redirect_uri(),
        "state": "qb_auth",
    }
    url = f"{AUTH_URL}?{urlencode(params)}"

    print(f"\nOpening browser for QuickBooks authorization...")
    print(f"If the browser doesn't open, visit this URL manually:\n{url}\n")
    webbrowser.open(url)

    if _environment() == "production":
        return _run_manual_callback()
    else:
        return _run_local_callback()


def _run_local_callback() -> dict:
    """Catch OAuth callback on localhost:8080 (sandbox only)."""
    auth_code = None
    realm_id = None

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            nonlocal auth_code, realm_id
            qs = parse_qs(urlparse(self.path).query)
            auth_code = qs.get("code", [None])[0]
            realm_id = qs.get("realmId", [None])[0]
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"<h2>Authorization complete. You can close this tab.</h2>")
            threading.Thread(target=self.server.shutdown).start()

        def log_message(self, *args):
            pass

    HTTPServer(("localhost", 8080), CallbackHandler).serve_forever()

    tokens = _exchange_code(auth_code, realm_id)
    _save_tokens(tokens["access_token"], tokens["refresh_token"], realm_id)
    print(f"Tokens saved. Realm ID: {realm_id}")
    return {**tokens, "realm_id": realm_id}


def _run_manual_callback() -> dict:
    """Production auth — user copies code and realmId from GitHub Pages callback."""
    print("After authorizing in the browser, you will be redirected to:")
    print("  https://ncurtis91.github.io/curtis-qb-app/callback")
    print("\nCopy the two values shown on that page and paste them below.\n")

    auth_code = input("Authorization Code: ").strip()
    realm_id  = input("Realm ID:           ").strip()

    tokens = _exchange_code(auth_code, realm_id)
    _save_tokens(tokens["access_token"], tokens["refresh_token"], realm_id)
    print(f"Tokens saved. Realm ID: {realm_id}")
    return {**tokens, "realm_id": realm_id}


def get_tokens() -> dict:
    """
    Return valid tokens dict with keys: access_token, refresh_token, realm_id.
    Refreshes if saved tokens exist, runs full OAuth flow if not.
    """
    saved = _load_tokens()

    if saved:
        try:
            refreshed = _refresh_tokens(saved["refresh_token"])
            _save_tokens(refreshed["access_token"], refreshed["refresh_token"], saved["realm_id"])
            print("Tokens refreshed.")
            return {**refreshed, "realm_id": saved["realm_id"]}
        except Exception as e:
            print(f"Token refresh failed ({e}), re-authorizing...")

    return _run_oauth_flow()


def _base_url(tokens: dict) -> str:
    env = _environment()
    host = "https://sandbox-quickbooks.api.intuit.com" if env == "sandbox" else "https://quickbooks.api.intuit.com"
    return f"{host}/v3/company/{tokens['realm_id']}"


def api_get(path: str, tokens: dict) -> dict:
    """Make a GET request to the QBO API. path is relative to /v3/company/{realmId}/"""
    url = f"{_base_url(tokens)}/{path}"
    resp = requests.get(url, headers={
        "Authorization": f"Bearer {tokens['access_token']}",
        "Accept": "application/json",
    })
    resp.raise_for_status()
    return resp.json()


def api_post(path: str, tokens: dict, payload: dict) -> dict:
    """Make a POST request to the QBO API. path is relative to /v3/company/{realmId}/"""
    url = f"{_base_url(tokens)}/{path}?minorversion=65"
    resp = requests.post(url, headers={
        "Authorization": f"Bearer {tokens['access_token']}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }, json=payload)
    resp.raise_for_status()
    return resp.json()
