from __future__ import annotations

import os
import time
import uuid

import pytest
import requests


BASE_URL = os.getenv("PS13_API_BASE", "http://localhost:8000")
ADMIN_KEY = os.getenv("PS13_ADMIN_KEY", "orga_admin_key")
CONTRIB_KEY = os.getenv("PS13_CONTRIB_KEY", "carl_contrib_key")
ANALYST_KEY = os.getenv("PS13_ANALYST_KEY", "ana_analyst_key")


def _url(path: str) -> str:
    return f"{BASE_URL.rstrip('/')}{path}"


def _headers(api_key: str) -> dict[str, str]:
    return {"X-API-Key": api_key}


@pytest.fixture(scope="session", autouse=True)
def ensure_api_up():
    last_error = "unknown"
    for _ in range(30):
        try:
            resp = requests.get(_url("/api/health"), timeout=5)
            if resp.status_code == 200:
                return
            last_error = f"status={resp.status_code} body={resp.text[:200]}"
        except Exception as exc:  # pragma: no cover - network timing only
            last_error = str(exc)
        time.sleep(2)
    pytest.skip(f"API unavailable after retries: {last_error}")


def test_health_and_ready():
    r1 = requests.get(_url("/api/health"), timeout=10)
    assert r1.status_code == 200
    assert r1.json()["status"] == "ok"

    r2 = requests.get(_url("/api/ready"), timeout=10)
    assert r2.status_code == 200
    assert r2.json()["status"] == "ready"


def test_login_and_whoami():
    login = requests.post(
        _url("/api/auth/login"),
        json={"api_key": ADMIN_KEY},
        timeout=10,
    )
    assert login.status_code == 200
    body = login.json()
    token = body["access_token"]
    assert token
    assert body["user"]["role"] == "org_admin"

    who = requests.get(
        _url("/api/auth/whoami"),
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    assert who.status_code == 200
    assert who.json()["auth_type"] == "jwt"


def test_ingest_text_and_feed_visibility():
    unique_val = f"malware probe {uuid.uuid4().hex[:12]}"
    payload = {"text": f"{unique_val}|detected suspicious c2 beaconing", "source": "pytest"}
    ingest = requests.post(
        _url("/api/ingest/text"),
        headers=_headers(CONTRIB_KEY),
        json=payload,
        timeout=20,
    )
    assert ingest.status_code == 200
    assert ingest.json()["created"] >= 0

    feed = requests.get(
        _url("/api/feed?hours=24&limit=100"),
        headers=_headers(ADMIN_KEY),
        timeout=20,
    )
    assert feed.status_code == 200
    items = feed.json()["items"]
    assert isinstance(items, list)
    assert len(items) > 0
    assert all("classification_labels" in row for row in items[:5])


def test_integrity_verify_anchor_and_history():
    verify = requests.get(
        _url("/api/integrity/verify"),
        headers=_headers(ANALYST_KEY),
        timeout=10,
    )
    assert verify.status_code == 200
    assert verify.json()["status"] in {"PASS", "FAIL"}

    anchor = requests.post(
        _url("/api/integrity/anchor"),
        headers=_headers(ANALYST_KEY),
        timeout=10,
    )
    assert anchor.status_code == 200
    assert "created" in anchor.json()

    anchors = requests.get(
        _url("/api/integrity/anchors?limit=5"),
        headers=_headers(ANALYST_KEY),
        timeout=10,
    )
    assert anchors.status_code == 200
    rows = anchors.json()
    assert isinstance(rows, list)
    if rows:
        assert {"id", "up_to_ledger_id", "head_hash", "anchor_hash", "created_at"}.issubset(rows[0].keys())


def test_admin_overview_users_policies_and_runs():
    overview = requests.get(
        _url("/api/admin/overview"),
        headers=_headers(ADMIN_KEY),
        timeout=10,
    )
    assert overview.status_code == 200
    overview_body = overview.json()
    assert overview_body["org_name"] == "OrgA"
    assert overview_body["user_count"] >= 1
    assert "generated_at" in overview_body

    users = requests.get(
        _url("/api/admin/users"),
        headers=_headers(ADMIN_KEY),
        timeout=10,
    )
    assert users.status_code == 200
    user_rows = users.json()
    assert isinstance(user_rows, list)
    assert any(row["role"] == "org_admin" for row in user_rows)

    policies = requests.get(
        _url("/api/admin/federation-policies"),
        headers=_headers(ADMIN_KEY),
        timeout=10,
    )
    assert policies.status_code == 200
    policy_rows = policies.json()
    assert isinstance(policy_rows, list)
    assert len(policy_rows) >= 1

    first_policy = policy_rows[0]
    patched = requests.patch(
        _url(f"/api/admin/federation-policies/{first_policy['id']}"),
        headers=_headers(ADMIN_KEY),
        json={"min_credibility": first_policy["min_credibility"]},
        timeout=10,
    )
    assert patched.status_code == 200
    assert patched.json()["id"] == first_policy["id"]

    runs = requests.get(
        _url("/api/admin/ingestion-runs?limit=5"),
        headers=_headers(ADMIN_KEY),
        timeout=10,
    )
    assert runs.status_code == 200
    run_rows = runs.json()
    assert isinstance(run_rows, list)
    if run_rows:
        assert {"source_id", "status", "trigger", "created_count", "started_at"}.issubset(run_rows[0].keys())


def test_admin_ingestion_source_endpoints():
    sources = requests.get(
        _url("/api/admin/ingestion-sources"),
        headers=_headers(ADMIN_KEY),
        timeout=10,
    )
    assert sources.status_code == 200
    rows = sources.json()
    assert isinstance(rows, list)
    assert len(rows) >= 1

    source_id = rows[0]["id"]
    original_interval = rows[0]["interval_minutes"]

    updated = requests.patch(
        _url(f"/api/admin/ingestion-sources/{source_id}"),
        headers=_headers(ADMIN_KEY),
        json={"interval_minutes": original_interval},
        timeout=10,
    )
    assert updated.status_code == 200
    assert updated.json()["interval_minutes"] == original_interval

    queued = requests.post(
        _url(f"/api/admin/ingestion-sources/{source_id}/run"),
        headers=_headers(ADMIN_KEY),
        timeout=10,
    )
    assert queued.status_code == 200
    assert queued.json()["queued"] is True

    due = requests.post(
        _url("/api/admin/ingestion/run-due"),
        headers=_headers(ADMIN_KEY),
        timeout=10,
    )
    assert due.status_code == 200
    assert due.json()["queued"] is True


def test_source_reliability_endpoints():
    rows = requests.get(
        _url("/api/source-reliability"),
        headers=_headers(ANALYST_KEY),
        timeout=10,
    )
    assert rows.status_code == 200
    reliability_rows = rows.json()
    assert isinstance(reliability_rows, list)
    assert len(reliability_rows) >= 1

    first_row = reliability_rows[0]
    updated = requests.patch(
        _url(f"/api/source-reliability/{first_row['id']}"),
        headers=_headers(ANALYST_KEY),
        json={"reliability": first_row["reliability"], "weight": first_row["weight"]},
        timeout=10,
    )
    assert updated.status_code == 200
    assert updated.json()["id"] == first_row["id"]
