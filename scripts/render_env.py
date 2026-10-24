#!/usr/bin/env python3
"""Send the approval-gated MCP settings to the Render API service, then redeploy it.

Sets REPLY_DESK_MCP=on, REPLY_DESK_DOC_ID, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, and
GOOGLE_TOKEN_JSON on `reply-desk-api`, one variable at a time, so every other variable
on the service is left as it is. Values come from the root .env and
mcp-server/data/google-token.json. The token is checked with Google first, so an
expired one is never sent. Only variable names are printed, never values.

The Render API key is read from RENDER_API_KEY or ~/.render-api-key. With
--save-access-code, the service's ACCESS_CODE is also saved to ~/.reply-desk-access-code
(mode 600) for `make e2e-prod`.

    uv run python scripts/render_env.py [--dry-run] [--save-access-code]   # or: make render-env
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TOKEN_PATH = ROOT / "mcp-server" / "data" / "google-token.json"
API = "https://api.render.com/v1"
SERVICE = "reply-desk-api"
KEY_FILE = Path.home() / ".render-api-key"
ACCESS_CODE_FILE = Path.home() / ".reply-desk-access-code"


def read_env() -> dict[str, str]:
    values: dict[str, str] = {}
    env_file = ROOT / ".env"
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            key, sep, value = line.partition("=")
            if sep and not key.startswith("#"):
                values[key.strip()] = value.strip()
    return values


def settings() -> dict[str, str]:
    env = read_env()
    missing = [key for key in ("REPLY_DESK_DOC_ID", "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET") if not env.get(key)]
    if missing:
        raise SystemExit(f"Missing in .env: {', '.join(missing)} (see mcp-server/README.md).")
    if not TOKEN_PATH.is_file():
        raise SystemExit("No Google token yet: run `make google-auth` first.")
    token = json.loads(TOKEN_PATH.read_text(encoding="utf-8"))
    check_token(env["GOOGLE_CLIENT_ID"], env["GOOGLE_CLIENT_SECRET"], token)
    return {
        "REPLY_DESK_MCP": "on",
        "REPLY_DESK_DOC_ID": env["REPLY_DESK_DOC_ID"],
        "GOOGLE_CLIENT_ID": env["GOOGLE_CLIENT_ID"],
        "GOOGLE_CLIENT_SECRET": env["GOOGLE_CLIENT_SECRET"],
        "GOOGLE_TOKEN_JSON": json.dumps(token, separators=(",", ":")),
    }


def check_token(client_id: str, client_secret: str, token: dict[str, Any]) -> None:
    body = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": token.get("refresh_token", ""),
            "grant_type": "refresh_token",
        }
    ).encode()
    try:
        urllib.request.urlopen(urllib.request.Request("https://oauth2.googleapis.com/token", data=body), timeout=20)
    except urllib.error.HTTPError as exc:
        error = json.load(exc).get("error")
        raise SystemExit(f"The Google token does not work ({error}); run `make google-auth` again.") from exc


def render(method: str, path: str, key: str, body: dict[str, Any] | None = None) -> Any:
    request = urllib.request.Request(
        API + path,
        method=method,
        data=None if body is None else json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {key}", "Accept": "application/json", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            text = response.read().decode()
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"Render API {method} {path.split('?')[0]}: HTTP {exc.code}") from exc
    return json.loads(text) if text else None


def find_service(key: str) -> str:
    items = render("GET", "/services?" + urllib.parse.urlencode({"name": SERVICE, "limit": 100}), key) or []
    for item in items:
        service = item.get("service", item)
        if service.get("name") == SERVICE:
            return service["id"]
    raise SystemExit(f"No Render service named {SERVICE} is visible to this API key.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="check the values and list the names; change nothing")
    parser.add_argument("--save-access-code", action="store_true", help=f"save ACCESS_CODE to {ACCESS_CODE_FILE}")
    args = parser.parse_args()

    values = settings()
    print("Google token works. Variables:", ", ".join(values))
    if args.dry_run:
        print("Dry run: nothing sent to Render.")
        return 0

    key = os.environ.get("RENDER_API_KEY", "").strip() or (KEY_FILE.read_text().strip() if KEY_FILE.is_file() else "")
    if not key:
        raise SystemExit(f"Set RENDER_API_KEY or save the key to {KEY_FILE} (chmod 600).")
    service_id = find_service(key)
    for name, value in values.items():
        render("PUT", f"/services/{service_id}/env-vars/{name}", key, {"value": value})
        print(f"set {name}")

    if args.save_access_code:
        found = render("GET", f"/services/{service_id}/env-vars/ACCESS_CODE", key) or {}
        code = found.get("value") or (found.get("envVar") or {}).get("value")
        if not code:
            raise SystemExit("ACCESS_CODE is not set on the service.")
        fd = os.open(ACCESS_CODE_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as handle:
            handle.write(code)
        print(f"saved ACCESS_CODE to {ACCESS_CODE_FILE}")

    deploy = render("POST", f"/services/{service_id}/deploys", key, {}) or {}
    print(f"Redeploy started ({deploy.get('id', 'id unknown')}). /api/health shows mcp.enabled once it is live.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
