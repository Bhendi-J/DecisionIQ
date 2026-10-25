"""Account workflows and authorization boundaries, exercised through real HTTP handlers."""

import hashlib
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from decisioniq.dashboard import store
from decisioniq.dashboard.auth import COOKIE
from decisioniq.main import app

PASSWORD = "Correct-horse-battery-2026"


@pytest.fixture
def accounts(tmp_path, monkeypatch):
    monkeypatch.setenv("DECISIONIQ_DB_PATH", str(tmp_path / "auth.sqlite3"))
    with TestClient(app) as client:
        yield client


def register(client, email="owner@example.com", company="Private company"):
    response = client.post(
        "/api/auth/register",
        json={
            "name": "Company owner",
            "email": email,
            "password": PASSWORD,
            "company_name": company,
            "currency": "GBP",
        },
    )
    assert response.status_code == 201, response.text
    client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    return response.json()


def login(client, email):
    response = client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    return response.json()


def test_anonymous_access_and_old_demo_bypass_are_closed(accounts):
    for path in [
        "/api/auth/me",
        "/api/bootstrap",
        "/api/dashboard",
        "/api/export/sales.csv",
        "/api/auth/members",
    ]:
        assert accounts.get(path).status_code == 401
    assert accounts.post("/api/demo/session", json={"company_id": "aster"}).status_code == 404
    assert accounts.post("/finance/predict", json={}).status_code == 401
    assert accounts.post("/api/auth/workspace", json={"company_id": "aster"}).status_code == 401


def test_registration_is_atomic_private_and_cannot_choose_admin(accounts):
    session = register(accounts, "Owner@Example.COM")
    assert session["user"]["email"] == "owner@example.com"
    assert session["user"]["is_admin"] is False
    assert len(session["companies"]) == 1
    company = session["companies"][0]
    assert company["role"] == "owner" and company["source_kind"] == "upload"
    assert accounts.get("/api/dashboard").json()["historical"] == []
    assert accounts.post("/api/auth/workspace", json={"company_id": "aster"}).status_code == 403
    assert accounts.post("/finance/predict", json={}).status_code == 403
    user = store.rows("SELECT * FROM users WHERE id=?", (session["user"]["id"],))[0]
    assert user["password_hash"].startswith("scrypt$131072$8$1$")
    assert PASSWORD not in user["password_hash"]
    cookie = accounts.cookies.get(COOKIE)
    saved = store.rows("SELECT * FROM sessions WHERE user_id=?", (user["id"],))[0]
    assert saved["token_hash"] == hashlib.sha256(cookie.encode()).hexdigest()
    assert cookie != saved["token_hash"]
    original_count = store.rows("SELECT COUNT(*) AS n FROM companies")[0]["n"]
    duplicate = accounts.post(
        "/api/auth/register",
        json={
            "name": "Duplicate",
            "email": "owner@example.com",
            "password": PASSWORD,
            "company_name": "Unwanted duplicate",
        },
    )
    assert duplicate.status_code == 409
    assert store.rows("SELECT COUNT(*) AS n FROM companies")[0]["n"] == original_count
    for extra in [{"is_admin": True}, {"role": "admin"}]:
        response = accounts.post(
            "/api/auth/register",
            json={
                "name": "Attacker",
                "email": "other@example.com",
                "password": PASSWORD,
                "company_name": "Example",
                **extra,
            },
        )
        assert response.status_code == 422
    weak = accounts.post(
        "/api/auth/register",
        json={
            "name": "Example",
            "email": "weak@example.com",
            "password": "12345678",
            "company_name": "Example",
        },
    )
    assert weak.status_code == 422


def test_login_cookie_rotation_logout_and_expiry(accounts):
    register(accounts)
    first = accounts.cookies.get(COOKIE)
    response = accounts.post(
        "/api/auth/login", json={"email": "owner@example.com", "password": PASSWORD}
    )
    assert response.status_code == 200
    assert "httponly" in response.headers["set-cookie"].lower()
    assert "samesite=strict" in response.headers["set-cookie"].lower()
    accounts.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    second = accounts.cookies.get(COOKIE)
    assert first != second
    assert not store.rows(
        "SELECT * FROM sessions WHERE token_hash=?", (hashlib.sha256(first.encode()).hexdigest(),)
    )
    assert accounts.post("/api/auth/logout").status_code == 204
    assert accounts.get("/api/dashboard").status_code == 401
    accounts.cookies.set(COOKIE, second)
    assert accounts.get("/api/auth/me").status_code == 401
    accounts.cookies.clear()
    login(accounts, "owner@example.com")
    with store.connect() as connection:
        connection.execute(
            "UPDATE sessions SET expires_at=?", ((store.now() - timedelta(seconds=1)).isoformat(),)
        )
    assert accounts.get("/api/auth/me").status_code == 401


def test_csrf_and_cross_origin_requests_are_rejected(accounts):
    register(accounts)
    csrf = accounts.headers.pop("X-CSRF-Token")
    assert accounts.post("/api/settings/api-key").status_code == 403
    assert accounts.post("/api/auth/logout").status_code == 403
    assert (
        accounts.post(
            "/api/uploads", files={"file": ("x.csv", b"date,sales\n2026-01-01,1")}
        ).status_code
        == 403
    )
    accounts.headers["X-CSRF-Token"] = csrf
    assert (
        accounts.post(
            "/api/settings/api-key", headers={"Origin": "https://attacker.example"}
        ).status_code
        == 403
    )
    assert (
        accounts.post(
            "/api/auth/login",
            json={"email": "owner@example.com", "password": PASSWORD},
            headers={"Origin": "https://attacker.example"},
        ).status_code
        == 403
    )
    assert (
        accounts.post(
            "/api/auth/register",
            json={
                "name": "Attacker",
                "email": "attack@example.com",
                "password": PASSWORD,
                "company_name": "Example",
            },
            headers={"Sec-Fetch-Site": "cross-site"},
        ).status_code
        == 403
    )
    assert (
        accounts.post("/api/settings/api-key", headers={"Origin": "http://testserver"}).status_code
        == 200
    )


def test_company_membership_roles_and_immediate_revocation(accounts):
    owner = register(accounts)
    company_id = owner["company_id"]
    owner_id = owner["user"]["id"]
    teammate = register(accounts, "teammate@example.com", "Other company")
    own_company = teammate["company_id"]
    member_id = teammate["user"]["id"]
    assert accounts.post("/api/auth/workspace", json={"company_id": company_id}).status_code == 403
    login(accounts, "owner@example.com")
    assert (
        accounts.post(
            "/api/auth/members", json={"email": "teammate@example.com", "role": "member"}
        ).status_code
        == 201
    )
    assert accounts.delete(f"/api/auth/members/{owner_id}").status_code == 409
    assert accounts.get("/api/auth/members").status_code == 200
    login(accounts, "teammate@example.com")
    view = accounts.get("/api/auth/me").json()
    assert {c["id"] for c in view["companies"]} == {company_id, own_company}
    assert accounts.post("/api/auth/workspace", json={"company_id": company_id}).status_code == 200
    dashboard = accounts.get("/api/dashboard")
    assert dashboard.status_code == 200
    assert dashboard.json()["company"]["role"] == "member"
    assert accounts.get("/api/export/sales.csv").status_code == 200
    assert (
        accounts.post(
            "/api/uploads", files={"file": ("x.csv", b"date,sales\n2026-01-01,1")}
        ).status_code
        == 201
    )
    assert accounts.patch("/api/settings", json={"api_state": "active"}).status_code == 403
    assert accounts.post("/api/settings/api-key").status_code == 403
    assert accounts.get("/api/auth/members").status_code == 403
    assert (
        accounts.post(
            "/api/auth/members", json={"email": "teammate@example.com", "role": "owner"}
        ).status_code
        == 403
    )
    # Revocation is checked on every request, even for an already-issued session.
    member_cookie = accounts.cookies.get(COOKIE)
    member_csrf = accounts.headers["X-CSRF-Token"]
    accounts.cookies.clear()
    login(accounts, "owner@example.com")
    assert accounts.delete(f"/api/auth/members/{member_id}").status_code == 204
    accounts.cookies.clear()
    accounts.cookies.set(COOKIE, member_cookie)
    accounts.headers["X-CSRF-Token"] = member_csrf
    assert accounts.get("/api/dashboard").status_code == 403
    assert {c["id"] for c in accounts.get("/api/auth/me").json()["companies"]} == {own_company}
    assert accounts.post("/api/auth/workspace", json={"company_id": own_company}).status_code == 200


def test_admin_access_is_local_provisioned_and_legacy_keys_still_scoped(accounts):
    account = register(accounts)
    with store.connect() as connection:
        connection.execute("UPDATE users SET is_admin=1 WHERE id=?", (account["user"]["id"],))
    session = login(accounts, "owner@example.com")
    assert session["user"]["is_admin"] is True
    assert {"aster", "maison", "nordhaus"}.issubset({c["id"] for c in session["companies"]})
    assert accounts.post("/api/auth/workspace", json={"company_id": "aster"}).status_code == 200
    assert accounts.post("/finance/predict", json={}).status_code == 200
    assert accounts.get("/api/bootstrap").headers["cache-control"] == "no-store"


def test_failed_login_messages_and_throttling(accounts, monkeypatch):
    register(accounts)
    monkeypatch.setattr("decisioniq.dashboard.auth.verify_password", lambda *_: False)
    unknown = accounts.post(
        "/api/auth/login", json={"email": "unknown@example.com", "password": "bad"}
    )
    bad = accounts.post("/api/auth/login", json={"email": "owner@example.com", "password": "bad"})
    assert unknown.status_code == bad.status_code == 401
    assert unknown.json() == bad.json()
    for _ in range(9):
        assert (
            accounts.post(
                "/api/auth/login", json={"email": "owner@example.com", "password": "bad"}
            ).status_code
            == 401
        )
    limited = accounts.post(
        "/api/auth/login", json={"email": "owner@example.com", "password": "bad"}
    )
    assert limited.status_code == 429 and "retry-after" in limited.headers


def test_access_upgrade_preserves_sales_and_revokes_only_legacy_credentials_once(accounts):
    account = register(accounts)
    company_id = account["company_id"]
    key = accounts.post("/api/settings/api-key").json()["key"]
    accounts.patch("/api/settings", json={"api_state": "active"})
    payload = {
        "currency": "GBP",
        "records": [{"record_id": "preserved-1", "date": "2026-01-01", "sales": 75}],
    }
    assert (
        accounts.post("/api/intake/sales", headers={"X-API-Key": key}, json=payload).status_code
        == 202
    )
    with store.connect() as connection:
        connection.execute("DELETE FROM config WHERE name='account_auth_v1'")
    store.initialize()
    assert (
        accounts.post("/api/intake/sales", headers={"X-API-Key": key}, json=payload).status_code
        == 401
    )
    assert accounts.get("/api/dashboard").json()["historical"][0]["sales"] == 75
    assert (
        store.rows("SELECT company_id FROM memberships WHERE user_id=?", (account["user"]["id"],))[
            0
        ]["company_id"]
        == company_id
    )
    replacement = accounts.post("/api/settings/api-key").json()["key"]
    store.initialize()
    assert (
        accounts.post(
            "/api/intake/sales", headers={"X-API-Key": replacement}, json=payload
        ).status_code
        == 202
    )
