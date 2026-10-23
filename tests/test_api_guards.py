"""Deployment Phase 2 exit: PII never leaves, CORS, the access code, the rate limit, body size."""

import json
import logging

from support_reply.fixtures import CLEAN_HIT, PII_COMPLAINT, RAW_PAN, RAW_PHONE

ALLOWED = "https://reply-desk.example"


def _no_raw(text):
    return RAW_PAN not in text and RAW_PHONE not in text


# --- PII --------------------------------------------------------------------------------


def test_a_pii_complaint_never_comes_back_or_reaches_the_logs(api, caplog):
    caplog.set_level(logging.DEBUG)
    client = api()

    created = client.post("/api/sessions", json={"complaint": PII_COMPLAINT})
    session_id = created.json()["session_id"]
    bodies = [
        created.text,
        client.get(f"/api/sessions/{session_id}").text,
        client.get("/api/sessions").text,
        client.post(f"/api/sessions/{session_id}/refine", json={"pushback": f"Shorter, PAN {RAW_PAN}"}).text,
        client.post(
            f"/api/sessions/{session_id}/messages", json={"message": f"call me on {RAW_PHONE}"}
        ).text,
        client.post(f"/api/sessions/{session_id}/approve").text,
        client.get("/api/records").text,
        client.get(f"/api/records/{session_id}/email").text,
    ]

    for body in bodies:
        assert _no_raw(body), body
    assert "[PAN]" in bodies[0]
    assert _no_raw(caplog.text)
    for path in client.out_dir.rglob("*"):
        if path.is_file():
            assert _no_raw(path.read_text())


def test_invalid_bodies_never_echo_what_was_sent(api, caplog):
    caplog.set_level(logging.DEBUG)
    client = api()
    attempts = [
        {"json": {"complaint": RAW_PAN * 250}},  # too long
        {"json": {"complaint": 5, "note": RAW_PAN}},  # wrong type, extra field
        {"json": {"pushback": f"PAN {RAW_PAN}"}},  # wrong field
        {"json": [RAW_PAN, RAW_PHONE]},  # not an object
        {
            "content": f'{{"complaint": "my PAN is {RAW_PAN} and phone {RAW_PHONE}',  # broken JSON
            "headers": {"content-type": "application/json"},
        },
    ]

    for attempt in attempts:
        response = client.post("/api/sessions", **attempt)
        assert response.status_code == 400, response.text
        assert _no_raw(response.text), response.text
        assert response.json()["error"] == "invalid_request"
        for field in response.json()["fields"]:
            assert set(field) == {"field", "type"}
    assert _no_raw(caplog.text)


def test_server_errors_are_generic_and_carry_a_request_id(api, caplog):
    caplog.set_level(logging.DEBUG)

    def broken_models():
        raise RuntimeError(f"boom {RAW_PAN}")

    client = api(models=broken_models, raise_server_exceptions=False)

    response = client.post("/api/sessions", json={"complaint": PII_COMPLAINT})

    assert response.status_code == 500
    body = response.json()
    assert body["error"] == "internal_error"
    assert body["request_id"] == response.headers["x-request-id"]
    assert _no_raw(response.text)
    assert _no_raw(caplog.text)
    assert "RuntimeError" in caplog.text


def test_a_server_error_is_still_readable_cross_origin(api):
    def broken_models():
        raise RuntimeError("boom")

    client = api(models=broken_models, allowed_origins=(ALLOWED,))

    response = client.post("/api/sessions", json={"complaint": CLEAN_HIT}, headers={"Origin": ALLOWED})

    assert response.status_code == 500
    assert response.headers["access-control-allow-origin"] == ALLOWED


def test_every_response_carries_a_request_id(api):
    response = api().get("/api/health")
    assert len(response.headers["x-request-id"]) == 32


# --- CORS -------------------------------------------------------------------------------


def _preflight(client, origin):
    return client.options(
        "/api/sessions",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,x-access-code",
        },
    )


def test_cors_allows_the_listed_origin_and_rejects_others(api):
    client = api(allowed_origins=(ALLOWED,))

    ok = _preflight(client, ALLOWED)
    assert ok.status_code == 200
    assert ok.headers["access-control-allow-origin"] == ALLOWED
    assert "x-access-code" in ok.headers["access-control-allow-headers"].lower()

    evil = _preflight(client, "https://evil.example")
    assert evil.status_code == 400
    assert "access-control-allow-origin" not in evil.headers

    simple = client.get("/api/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in simple.headers
    allowed = client.get("/api/health", headers={"Origin": ALLOWED})
    assert allowed.headers["access-control-allow-origin"] == ALLOWED


def test_cors_regex_admits_preview_urls_only(api):
    client = api(allowed_origin_regex=r"https://reply-desk-web-pr-\d+\.onrender\.com")

    preview = _preflight(client, "https://reply-desk-web-pr-12.onrender.com")
    other = _preflight(client, "https://someone-else.onrender.com")

    assert preview.status_code == 200
    assert other.status_code == 400


def test_without_origins_no_cors_headers_are_sent(api):
    response = api().get("/api/health", headers={"Origin": ALLOWED})
    assert "access-control-allow-origin" not in response.headers


def test_error_responses_still_carry_cors_headers(api):
    client = api(allowed_origins=(ALLOWED,), access_code="s3cret")
    response = client.get("/api/sessions", headers={"Origin": ALLOWED})
    assert response.status_code == 401
    assert response.headers["access-control-allow-origin"] == ALLOWED


# --- access code ------------------------------------------------------------------------


def test_the_access_code_guards_every_route_but_health(api):
    client = api(access_code="s3cret")

    assert client.get("/api/health").status_code == 200
    assert client.get("/api/health").json()["access_code_required"] is True
    assert client.get("/api/sessions").status_code == 401
    assert client.get("/api/sessions", headers={"X-Access-Code": "wrong"}).status_code == 401
    missing = client.post("/api/sessions", json={"complaint": CLEAN_HIT})
    assert missing.status_code == 401
    assert missing.json()["error"] == "access_code_required"
    assert client.get("/api/records").status_code == 401
    assert client.post("/api/acceptance/run").status_code == 401

    ok = client.post(
        "/api/sessions", json={"complaint": CLEAN_HIT}, headers={"X-Access-Code": "s3cret"}
    )
    assert ok.status_code == 200


# --- rate limit and body size -----------------------------------------------------------


def test_the_thirteenth_turn_in_a_minute_from_one_ip_is_429(api):
    client = api()
    session_id = client.post("/api/sessions", json={"complaint": CLEAN_HIT}).json()["session_id"]
    for _ in range(5):
        client.post(f"/api/sessions/{session_id}/refine", json={"pushback": "Shorter"})
    for _ in range(6):
        assert client.post("/api/sessions", json={"complaint": CLEAN_HIT}).status_code == 200

    thirteenth = client.post("/api/sessions", json={"complaint": CLEAN_HIT})

    assert thirteenth.status_code == 429
    assert thirteenth.json()["error"] == "rate_limited"
    # Reads are not turns.
    assert client.get("/api/sessions").status_code == 200


def test_the_rate_limit_keys_on_the_proxy_appended_hop(api):
    client = api(rate_per_minute=1)

    def post(forwarded):
        return client.post(
            "/api/sessions", json={"complaint": CLEAN_HIT}, headers={"X-Forwarded-For": forwarded}
        ).status_code

    assert post("1.1.1.1, 10.0.0.1") == 200
    # A forged left-most hop does not buy a fresh bucket: the proxy's hop is the key.
    assert post("9.9.9.9, 10.0.0.1") == 429
    assert post("10.0.0.2") == 200


def test_the_client_ip_header_keys_the_rate_limit_when_set(api):
    # As on Render: every request shares the proxy's last X-Forwarded-For hop.
    client = api(rate_per_minute=1, client_ip_header="CF-Connecting-IP")

    def post(**headers):
        return client.post(
            "/api/sessions",
            json={"complaint": CLEAN_HIT},
            headers={"X-Forwarded-For": "1.1.1.1, 10.0.0.1", **headers},
        ).status_code

    assert post(**{"CF-Connecting-IP": "1.1.1.1"}) == 200
    assert post(**{"CF-Connecting-IP": "2.2.2.2"}) == 200
    assert post(**{"CF-Connecting-IP": "1.1.1.1"}) == 429
    # Without the header, the last X-Forwarded-For hop is the key again.
    assert post() == 200
    assert post() == 429


def test_the_client_ip_header_is_ignored_when_not_configured(api):
    client = api(rate_per_minute=1)

    def post(cf_ip):
        return client.post(
            "/api/sessions",
            json={"complaint": CLEAN_HIT},
            headers={"X-Forwarded-For": "10.0.0.1", "CF-Connecting-IP": cf_ip},
        ).status_code

    assert post("1.1.1.1") == 200
    # A forged header does not buy a fresh bucket.
    assert post("2.2.2.2") == 429


def test_settings_read_the_client_ip_header_from_the_environment():
    from support_reply.api.settings import Settings

    assert Settings.from_env({}).client_ip_header is None
    assert Settings.from_env({"REPLY_DESK_CLIENT_IP_HEADER": " CF-Connecting-IP "}).client_ip_header == (
        "CF-Connecting-IP"
    )


def test_bodies_over_8kb_are_413_before_parsing(api):
    client = api()
    big = json.dumps({"complaint": "x" * 9000})

    declared = client.post("/api/sessions", content=big, headers={"content-type": "application/json"})
    assert declared.status_code == 413
    assert declared.json()["error"] == "payload_too_large"

    def chunks():
        yield big[:5000].encode()
        yield big[5000:].encode()

    streamed = client.post("/api/sessions", content=chunks(), headers={"content-type": "application/json"})
    assert streamed.status_code == 413
