#!/usr/bin/env python3
"""Sign in to Google once for the MCP server and save its token.

Opens Google's consent page in the browser and waits (up to 10 minutes) for the
redirect to a one-time listener on http://127.0.0.1:8765/. The code is exchanged
there, so it is never pasted anywhere, and the token is saved to
mcp-server/data/google-token.json (gitignored, mode 600). Nothing secret is printed.

The OAuth client comes from GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in the shell or
the root .env. While the Google app is in Testing mode the token lasts 7 days: run this
again, then `make render-env`, when drafts start failing with AUTHENTICATION_FAILED.

    uv run python scripts/google_auth.py     # or: make google-auth
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOKEN_PATH = ROOT / "mcp-server" / "data" / "google-token.json"
PORT = 8765
REDIRECT = f"http://127.0.0.1:{PORT}/"
SCOPES = "https://www.googleapis.com/auth/gmail.compose https://www.googleapis.com/auth/documents"
WAIT_SECONDS = 600


def read_env() -> dict[str, str]:
    values: dict[str, str] = {}
    env_file = ROOT / ".env"
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            key, sep, value = line.partition("=")
            if sep and not key.startswith("#"):
                values[key.strip()] = value.strip()
    values.update({key: value for key, value in os.environ.items() if value})
    return values


def main() -> int:
    env = read_env()
    client_id, client_secret = env.get("GOOGLE_CLIENT_ID"), env.get("GOOGLE_CLIENT_SECRET")
    if not client_id or not client_secret:
        print("Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env first (see mcp-server/README.md).")
        return 1

    state = secrets.token_urlsafe(24)
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(
        {
            "client_id": client_id,
            "redirect_uri": REDIRECT,
            "response_type": "code",
            "scope": SCOPES,
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
    )

    result: dict[str, str] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if query.get("state", [""])[0] == state and "code" in query:
                result["code"] = query["code"][0]
                message = "Signed in. The token is saved; you can close this tab."
            else:
                result["error"] = query.get("error", ["state mismatch or no code"])[0]
                message = "Sign-in did not complete. You can close this tab."
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(message.encode())

        def log_message(self, *args: object) -> None:  # keeps the code out of any log
            pass

    server = HTTPServer(("127.0.0.1", PORT), Handler)
    server.timeout = WAIT_SECONDS
    print("Opening Google sign-in. If no browser opens, visit:\n" + url, flush=True)
    webbrowser.open(url)
    server.handle_request()
    if "code" not in result:
        print("Sign-in failed:", result.get("error", "timed out waiting for the redirect"))
        return 1

    body = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "code": result["code"],
            "code_verifier": verifier,
            "grant_type": "authorization_code",
            "redirect_uri": REDIRECT,
        }
    ).encode()
    try:
        with urllib.request.urlopen(
            urllib.request.Request("https://oauth2.googleapis.com/token", data=body), timeout=30
        ) as response:
            token = json.load(response)
    except urllib.error.HTTPError as exc:
        print("Code exchange failed:", exc.code, json.load(exc).get("error"))
        return 1

    # The MCP server (googleapis) stores an absolute expiry.
    if "expires_in" in token:
        token["expiry_date"] = int((time.time() + token.pop("expires_in")) * 1000)
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(TOKEN_PATH, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(token, handle, indent=2)

    lifetime = token.get("refresh_token_expires_in")
    expires = (
        time.strftime("%d %b %Y", time.localtime(time.time() + lifetime))
        if lifetime
        else "no fixed expiry (app published)"
    )
    print(f"Saved {TOKEN_PATH.relative_to(ROOT)}. Scopes: {token.get('scope')}. Refresh token expires: {expires}.")
    print("Next: `make render-env` to send it to Render.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
