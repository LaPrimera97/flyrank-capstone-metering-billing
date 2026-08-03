def _headers(tenant, key):
    return {"X-API-Key": tenant["api_key"], "Idempotency-Key": key, "Content-Type": "application/json"}


def test_same_idempotency_key_creates_exactly_one_usage_event(client, free_tenant):
    body = {"usage_type": "api_call", "quantity": 1}

    r1 = client.post("/v1/generate", json=body, headers=_headers(free_tenant, "key-abc"))
    assert r1.status_code == 200
    assert r1.json()["idempotent_replay"] is False

    r2 = client.post("/v1/generate", json=body, headers=_headers(free_tenant, "key-abc"))
    assert r2.status_code == 200
    assert r2.json()["idempotent_replay"] is True

    # Same usage_event_id both times -> proves no second row was created.
    assert r1.json()["usage_event_id"] == r2.json()["usage_event_id"]

    usage = client.get("/usage", headers={"X-API-Key": free_tenant["api_key"]}).json()
    assert usage["api_calls_used"] == 1  # NOT 2


def test_retry_mirrors_original_response_even_with_different_body(client, free_tenant):
    """A client retrying after a dropped response might not perfectly replay the
    body; the idempotency key alone must govern dedup, and the ORIGINAL
    response is what gets mirrored back (never recomputed)."""
    r1 = client.post(
        "/v1/generate",
        json={"usage_type": "api_call", "quantity": 1},
        headers=_headers(free_tenant, "key-xyz"),
    )
    r2 = client.post(
        "/v1/generate",
        json={"usage_type": "api_call", "quantity": 5},  # different body, same key
        headers=_headers(free_tenant, "key-xyz"),
    )
    assert r1.json()["billable_quantity"] == r2.json()["billable_quantity"] == 1


def test_different_idempotency_keys_create_separate_events(client, free_tenant):
    client.post("/v1/generate", json={"usage_type": "api_call", "quantity": 1}, headers=_headers(free_tenant, "k1"))
    client.post("/v1/generate", json={"usage_type": "api_call", "quantity": 1}, headers=_headers(free_tenant, "k2"))

    usage = client.get("/usage", headers={"X-API-Key": free_tenant["api_key"]}).json()
    assert usage["api_calls_used"] == 2


def test_missing_idempotency_key_is_rejected(client, free_tenant):
    r = client.post(
        "/v1/generate",
        json={"usage_type": "api_call", "quantity": 1},
        headers={"X-API-Key": free_tenant["api_key"]},
    )
    assert r.status_code == 422


def test_missing_api_key_header_is_a_validation_error(client, free_tenant):
    r = client.post(
        "/v1/generate",
        json={"usage_type": "api_call", "quantity": 1},
        headers={"Idempotency-Key": "k1"},
    )
    assert r.status_code == 422


def test_invalid_api_key_is_rejected_with_401(client, free_tenant):
    r = client.post(
        "/v1/generate",
        json={"usage_type": "api_call", "quantity": 1},
        headers={"X-API-Key": "not-a-real-key", "Idempotency-Key": "k1"},
    )
    assert r.status_code == 401
