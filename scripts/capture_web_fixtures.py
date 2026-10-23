#!/usr/bin/env python3
"""Capture API responses for the frontend's Vitest fixtures.

Runs the FastAPI app in-process with models off and approvals in a temporary
directory, and writes `web/src/test/fixtures/api.json`: one session view per UI state,
plus a records list and an acceptance report. Rerun after changing the API:

    uv run python scripts/capture_web_fixtures.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "web" / "src" / "test" / "fixtures" / "api.json"


def main() -> int:
    sys.path.insert(0, str(ROOT / "src"))
    with tempfile.TemporaryDirectory(prefix="reply-desk-fixtures-") as out_dir:
        os.environ["REPLY_DESK_MODELS"] = "off"
        os.environ["REPLY_DESK_OUT_DIR"] = out_dir

        from fastapi.testclient import TestClient

        from support_reply.api.app import create_app
        from support_reply.api.settings import Settings
        from support_reply.fixtures import ADVICE_THREAD, BRANCHES
        from support_reply.llm import CUES_ONLY

        class FlagsTheSource:
            def classify(self, **_):
                return {"failures": [{"check": "advice", "span": "Source"}]}

        client = TestClient(create_app(Settings(rate_per_minute=1000)))
        blocked_client = TestClient(
            create_app(
                Settings(rate_per_minute=1000),
                models=lambda: {"classifier": CUES_ONLY, "review_classifier": FlagsTheSource()},
            )
        )

        def start(text: str, using: TestClient = client) -> dict:
            response = using.post("/api/sessions", json={"complaint": text})
            response.raise_for_status()
            return response.json()

        def refine(view: dict, pushback: str) -> dict:
            response = client.post(f"/api/sessions/{view['session_id']}/refine", json={"pushback": pushback})
            response.raise_for_status()
            return response.json()

        views = {name: start(text) for name, text in BRANCHES.items()}

        refuse = start(ADVICE_THREAD[0])
        for ask in ADVICE_THREAD[1:3]:
            refuse = client.post(
                f"/api/sessions/{refuse['session_id']}/messages", json={"message": ask}
            ).json()
        views["refuse"] = refuse
        views["blocked"] = start(BRANCHES["clean_hit"], blocked_client)
        views["disagree"] = start("The chart for HDFC Large Cap Fund shows the wrong NAV")

        refined = start(BRANCHES["clean_hit"])
        for pushback in (
            "Shorter",
            "They're asking about HDFC Gold ETF Fund of Fund",
            "Check if this is the fee issue from last week",
        ):
            refined = refine(refined, pushback)
        views["refined"] = refined

        exhausted = start(BRANCHES["clean_hit"])
        for _ in range(5):
            exhausted = refine(exhausted, "Shorter")
        views["exhausted"] = exhausted

        approved = start(BRANCHES["pii"])
        client.post(f"/api/sessions/{approved['session_id']}/approve").raise_for_status()
        views["approved"] = client.get(f"/api/sessions/{approved['session_id']}").json()
        start_miss = start(BRANCHES["corpus_miss"])
        client.post(f"/api/sessions/{start_miss['session_id']}/approve").raise_for_status()

        payload = {
            "views": views,
            "sessions": client.get("/api/sessions").json(),
            "records": client.get("/api/records").json(),
            "email": client.get(f"/api/records/{approved['session_id']}/email").json(),
            "acceptance": client.post("/api/acceptance/run").json(),
            "health": client.get("/api/health").json(),
        }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(views)} views)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
