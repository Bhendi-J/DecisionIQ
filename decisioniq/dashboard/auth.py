"""Signed local demo sessions and separately scoped company ingestion credentials."""

import base64
import hashlib
import hmac
import json
import os
import time

from fastapi import HTTPException, Request

from decisioniq.dashboard import store


def demo_enabled():
    return os.getenv("DECISIONIQ_DEMO_MODE", "1") == "1"


def token(company_id):
    payload = base64.urlsafe_b64encode(
        json.dumps({"company_id": company_id, "exp": time.time() + 43200}).encode()
    ).decode()
    secret = store.rows("SELECT value FROM config WHERE name='session_secret'")[0]["value"]
    return payload + "." + hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


def current_company(request: Request):
    value = request.cookies.get("decisioniq_session", "")
    try:
        payload, signature = value.rsplit(".", 1)
        secret = store.rows("SELECT value FROM config WHERE name='session_secret'")[0]["value"]
        expected = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError("Invalid session")
        data = json.loads(base64.urlsafe_b64decode(payload))
        if data["exp"] < time.time() or not demo_enabled():
            raise ValueError("Session expired")
        return store.company(data["company_id"])
    except (ValueError, KeyError, IndexError):
        raise HTTPException(401, "Choose a local demonstration workspace to continue.") from None


def intake_company(request: Request):
    value = request.headers.get("X-API-Key", "")
    digest = hashlib.sha256(value.encode()).hexdigest()
    records = store.rows("SELECT company_id FROM api_keys WHERE hash=?", (digest,))
    if not records:
        raise HTTPException(401, "A valid company-scoped X-API-Key is required.")
    company = store.company(records[0]["company_id"])
    if company["api_state"] != "active":
        raise HTTPException(
            409,
            {
                "code": "intake_paused",
                "message": "API intake is paused. Resume it in the Data Hub; manual uploads remain available.",
            },
        )
    return company
