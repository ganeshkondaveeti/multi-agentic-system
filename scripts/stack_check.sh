#!/usr/bin/env bash
# The production path, locally and offline.
#
# Starts the API with the Dockerfile's server command, builds the web app to call it
# directly (so every browser request crosses origins and goes through CORS, not the
# Vite proxy), and runs the Playwright suite against that build. Then it greps the API
# log (at DEBUG) and the records directory for the fixture PAN and phone.
set -euo pipefail

cd "$(dirname "$0")/.."

API_PORT=${API_PORT:-8000}
WEB_PORT=${WEB_PORT:-4174}
API_URL="http://127.0.0.1:${API_PORT}"
WEB_URL="http://127.0.0.1:${WEB_PORT}"
RAW_PAN=ABCDE1234F
RAW_PHONE=9876543210

WORK=$(mktemp -d)
LOG="$WORK/api.log"
OUT="$WORK/out"
pids=()

cleanup() {
  for pid in "${pids[@]}"; do kill "$pid" 2>/dev/null || true; done
  wait 2>/dev/null || true
}
trap cleanup EXIT

wait_for() {
  for _ in $(seq 1 60); do
    curl -fsS -o /dev/null "$1" 2>/dev/null && return 0
    sleep 1
  done
  echo "timed out waiting for $1" >&2
  return 1
}

echo "== API on $API_URL (models off, log $LOG)"
REPLY_DESK_MODELS=off \
REPLY_DESK_OUT_DIR="$OUT" \
REPLY_DESK_RATE_PER_MINUTE=1000 \
REPLY_DESK_ENV=e2e \
ACCESS_CODE= \
ALLOWED_ORIGINS="$WEB_URL" \
LOG_LEVEL=DEBUG \
  uv run --no-dev uvicorn support_reply.api.app:app --host 127.0.0.1 --port "$API_PORT" \
  --proxy-headers --forwarded-allow-ips='*' >"$LOG" 2>&1 &
pids+=($!)
wait_for "$API_URL/api/health"

echo "== CORS: allowed and refused origins"
allowed=$(curl -fsS -o /dev/null -D - -X OPTIONS "$API_URL/api/sessions" \
  -H "Origin: $WEB_URL" -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: content-type,x-access-code" | tr -d '\r')
grep -qi "^access-control-allow-origin: $WEB_URL$" <<<"$allowed" \
  || { echo "preflight from $WEB_URL was not allowed" >&2; exit 1; }
refused=$(curl -sS -o /dev/null -D - -X OPTIONS "$API_URL/api/sessions" \
  -H "Origin: https://evil.example" -H "Access-Control-Request-Method: POST" | tr -d '\r')
if grep -qi "^access-control-allow-origin:" <<<"$refused"; then
  echo "preflight from an unlisted origin was allowed" >&2; exit 1
fi

echo "== web build calling $API_URL directly, preview on $WEB_URL"
(cd web && VITE_API_BASE_URL="$API_URL" npm run build >/dev/null)
grep -rqF "$API_URL" web/dist/assets || { echo "the build does not call $API_URL" >&2; exit 1; }
# The preview still proxies /api for the tests' own `page.request` calls.
(cd web && VITE_DEV_API_TARGET="$API_URL" npx vite preview --host 127.0.0.1 --port "$WEB_PORT" --strictPort \
  >"$WORK/web.log" 2>&1) &
pids+=($!)
wait_for "$WEB_URL"

echo "== Playwright"
(cd web && E2E_BASE_URL="$WEB_URL" npx playwright test)

echo "== PII audit"
[ -s "$OUT/records.jsonl" ] || { echo "no records were written; the audit would prove nothing" >&2; exit 1; }
grep -qF "[PAN]" "$OUT/records.jsonl" || { echo "no PII-branch record found" >&2; exit 1; }
grep -qF "[PAN]" "$LOG" || { echo "the log never saw the PII turn; the audit would prove nothing" >&2; exit 1; }
for raw in "$RAW_PAN" "$RAW_PHONE"; do
  if grep -rqF "$raw" "$LOG" "$OUT"; then
    echo "raw PII found:" >&2
    grep -rlF "$raw" "$LOG" "$OUT" >&2
    exit 1
  fi
done
echo "no raw PAN or phone in $(wc -l <"$LOG" | tr -d ' ') log lines, $(wc -l <"$OUT/records.jsonl" | tr -d ' ') records, or $(ls "$OUT/email_drafts" | wc -l | tr -d ' ') email drafts"
echo "stack check passed"
