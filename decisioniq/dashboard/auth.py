"""Account authentication, revocable sessions, and organization authorization."""

import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import threading
from datetime import datetime, timedelta
from typing import Annotated, Literal
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator

from decisioniq.dashboard import store

router = APIRouter(prefix="/api/auth", tags=["Accounts"])
COOKIE = "foresight_session"
SESSION_HOURS = 12
_password_workers = threading.BoundedSemaphore(2)


def derive_password(password, salt):
    # Bound simultaneous 128 MiB derivations on a local/demo backend.
    with _password_workers:
        return hashlib.scrypt(
            password.encode(), salt=salt, n=2**17, r=8, p=1, maxmem=256 * 1024 * 1024
        ).hex()


def password_hash(password):
    salt = secrets.token_hex(16)
    digest = derive_password(password, bytes.fromhex(salt))
    return f"scrypt$131072$8$1${salt}${digest}"


def verify_password(password, encoded):
    # The dummy derivation gives unknown accounts the same expensive verification path.
    parts = (encoded or "scrypt$131072$8$1$" + "00" * 16 + "$" + "00" * 64).split("$")
    if len(parts) != 6 or parts[:4] != ["scrypt", "131072", "8", "1"]:
        return False
    digest = derive_password(password, bytes.fromhex(parts[4]))
    return hmac.compare_digest(digest, parts[5]) and encoded is not None


def normalized_email(value):
    value = value.strip().lower()
    if len(value) > 254 or not re.fullmatch(
        r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?\.[a-z]{2,}", value
    ):
        raise ValueError("Enter a valid email address")
    return value


def trusted_origin(request):
    """Reject cross-origin browser writes, including login and registration CSRF."""
    origin = request.headers.get("origin")
    expected = os.getenv("FORESIGHT_ORIGIN", "").rstrip("/") or str(request.base_url).rstrip("/")
    if request.headers.get("sec-fetch-site") == "cross-site" or (origin and origin != expected):
        raise HTTPException(403, "This request must come from the ForeSight application.")
    referer = request.headers.get("referer")
    if not origin and referer:
        parsed = urlsplit(referer)
        if f"{parsed.scheme}://{parsed.netloc}" != expected:
            raise HTTPException(403, "This request must come from the ForeSight application.")


def rate_limit(key, maximum, seconds, increment=True):
    key = hashlib.sha256(key.encode()).hexdigest()
    at = store.now()
    with store.connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute("SELECT * FROM auth_limits WHERE key=?", (key,)).fetchone()
        active = row and (at - datetime.fromisoformat(row["started_at"])).total_seconds() < seconds
        count = row["attempts"] if active else 0
        if count >= maximum:
            raise HTTPException(
                429,
                "Too many attempts. Please try again later.",
                headers={"Retry-After": str(seconds)},
            )
        if increment:
            connection.execute(
                "INSERT INTO auth_limits VALUES (?,?,?) ON CONFLICT(key) DO UPDATE SET started_at=excluded.started_at,attempts=excluded.attempts",
                (key, row["started_at"] if active else at.isoformat(), count + 1),
            )


def current_user(request: Request):
    value = request.cookies.get(COOKIE, "")
    rows = (
        store.rows(
            "SELECT s.*,u.email,u.name,u.is_admin FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=?",
            (hashlib.sha256(value.encode()).hexdigest(),),
        )
        if value
        else []
    )
    if not rows or datetime.fromisoformat(rows[0]["expires_at"]) <= store.now():
        raise HTTPException(401, "Sign in to your ForeSight account.")
    session = rows[0]
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        trusted_origin(request)
        if not hmac.compare_digest(request.headers.get("x-csrf-token", ""), session["csrf_token"]):
            raise HTTPException(
                403, "Your session could not verify this request. Refresh and try again."
            )
    return session


User = Annotated[dict, Depends(current_user)]


def require_admin(user: User):
    if not user["is_admin"]:
        raise HTTPException(403, "Administrator access is required.")
    return user


def company_role(user, company_id):
    if user["is_admin"]:
        return "admin"
    rows = store.rows(
        "SELECT role FROM memberships WHERE user_id=? AND company_id=?",
        (user["user_id"], company_id),
    )
    if not rows:
        raise HTTPException(403, "You do not have access to this company.")
    return rows[0]["role"]


def current_company(user: User):
    role = company_role(user, user["company_id"])
    try:
        company = store.company(user["company_id"])
    except ValueError:
        raise HTTPException(403, "Select an authorized company workspace.") from None
    return {**company, "role": role}


def owner_company(company: Annotated[dict, Depends(current_company)]):
    if company["role"] not in {"owner", "admin"}:
        raise HTTPException(
            403, "Only company owners can manage settings, credentials, and team access."
        )
    return company


def account_view(user):
    if user["is_admin"]:
        entries = store.rows("SELECT id FROM companies ORDER BY rowid")
    else:
        entries = store.rows(
            "SELECT company_id AS id FROM memberships WHERE user_id=? ORDER BY rowid",
            (user["user_id"],),
        )
    companies = [
        {**store.company(row["id"]), "role": company_role(user, row["id"])} for row in entries
    ]
    return {
        "user": {
            "id": user["user_id"],
            "name": user["name"],
            "email": user["email"],
            "is_admin": bool(user["is_admin"]),
        },
        "companies": companies,
        "company_id": user["company_id"]
        if any(c["id"] == user["company_id"] for c in companies)
        else None,
        "csrf_token": user["csrf_token"],
        "llm_enabled": False,
    }


def start_session(request, response, user_id, company_id):
    raw = secrets.token_urlsafe(32)
    hashed = hashlib.sha256(raw.encode()).hexdigest()
    old = request.cookies.get(COOKIE, "")
    with store.connect() as connection:
        connection.execute(
            "DELETE FROM sessions WHERE expires_at<=? OR token_hash=?",
            (store.stamp(), hashlib.sha256(old.encode()).hexdigest()),
        )
        connection.execute(
            "INSERT INTO sessions VALUES (?,?,?,?,?,?)",
            (
                hashed,
                user_id,
                company_id,
                secrets.token_urlsafe(32),
                (store.now() + timedelta(hours=SESSION_HOURS)).isoformat(),
                store.stamp(),
            ),
        )
    response.set_cookie(
        COOKIE,
        raw,
        httponly=True,
        samesite="strict",
        secure=request.url.scheme == "https" or os.getenv("FORESIGHT_SECURE_COOKIES") == "1",
        max_age=SESSION_HOURS * 3600,
    )
    response.delete_cookie("decisioniq_session")
    user = store.rows(
        "SELECT s.*,u.email,u.name,u.is_admin FROM sessions s JOIN users u ON u.id=s.user_id WHERE token_hash=?",
        (hashed,),
    )[0]
    return account_view(user)


class Credentials(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(max_length=254)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def email_address(cls, value):
        return normalized_email(value)


class Registration(Credentials):
    name: str = Field(min_length=2, max_length=80)
    company_name: str = Field(min_length=2, max_length=50)
    currency: str = "GBP"
    timezone: str = "Asia/Kolkata"
    password: str = Field(min_length=12, max_length=128)

    @field_validator("name", "company_name")
    @classmethod
    def not_blank(cls, value):
        if len(value.strip()) < 2:
            raise ValueError("Use at least two non-space characters")
        return value.strip()

    @field_validator("currency")
    @classmethod
    def valid_currency(cls, value):
        from decisioniq.dashboard.ingestion import CURRENCIES

        if value not in CURRENCIES:
            raise ValueError("Choose a supported currency")
        return value

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value):
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError:
            raise ValueError("Choose a valid IANA time zone") from None
        return value


class WorkspaceSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    company_id: str = Field(min_length=1, max_length=60)


@router.post("/register", status_code=201)
def register(body: Registration, request: Request, response: Response):
    trusted_origin(request)
    rate_limit("register:" + request.client.host, 20, 3600)
    encoded = password_hash(body.password)
    user_id = store.uid()
    try:
        with store.connect() as connection:
            connection.execute(
                "INSERT INTO users VALUES (?,?,?,?,0,?)",
                (user_id, body.email, body.name, encoded, store.stamp()),
            )
            company_id = store.create_workspace(
                body.company_name, body.currency, body.timezone, connection
            )
            connection.execute(
                "INSERT INTO memberships VALUES (?,?,'owner')", (user_id, company_id)
            )
    except sqlite3.IntegrityError:
        raise HTTPException(
            409, "An account with this email already exists. Sign in instead."
        ) from None
    return start_session(request, response, user_id, company_id)


@router.post("/login")
def login(body: Credentials, request: Request, response: Response):
    trusted_origin(request)
    rate_limit("login-ip:" + request.client.host, 100, 900)
    rate_limit("login-email:" + body.email, 10, 900, increment=False)
    users = store.rows("SELECT * FROM users WHERE email=?", (body.email,))
    if not verify_password(body.password, users[0]["password_hash"] if users else None):
        rate_limit("login-email:" + body.email, 10, 900)
        raise HTTPException(401, "Email or password is incorrect.")
    user = users[0]
    with store.connect() as connection:
        connection.execute(
            "DELETE FROM auth_limits WHERE key=?",
            (hashlib.sha256(("login-email:" + body.email).encode()).hexdigest(),),
        )
    entries = store.rows(
        "SELECT company_id FROM memberships WHERE user_id=? ORDER BY rowid LIMIT 1", (user["id"],)
    )
    if user["is_admin"]:
        entries = store.rows("SELECT id AS company_id FROM companies ORDER BY rowid LIMIT 1")
    return start_session(
        request, response, user["id"], entries[0]["company_id"] if entries else None
    )


@router.get("/me")
def me(user: User):
    return account_view(user)


@router.post("/logout", status_code=204)
def logout(response: Response, user: User):
    with store.connect() as connection:
        connection.execute("DELETE FROM sessions WHERE token_hash=?", (user["token_hash"],))
    response.delete_cookie(COOKIE)
    response.delete_cookie("decisioniq_session")


@router.post("/workspace")
def select_workspace(body: WorkspaceSelection, user: User):
    company_role(user, body.company_id)
    try:
        store.company(body.company_id)
    except ValueError:
        raise HTTPException(404, "Company not found") from None
    with store.connect() as connection:
        connection.execute(
            "UPDATE sessions SET company_id=? WHERE token_hash=?",
            (body.company_id, user["token_hash"]),
        )
    return account_view({**user, "company_id": body.company_id})


class MemberRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(max_length=254)
    role: Literal["owner", "member"] = "member"

    @field_validator("email")
    @classmethod
    def email_address(cls, value):
        return normalized_email(value)


Owner = Annotated[dict, Depends(owner_company)]


@router.get("/members")
def members(company: Owner):
    return store.rows(
        "SELECT u.id,u.name,u.email,m.role FROM memberships m JOIN users u ON m.user_id=u.id WHERE m.company_id=? ORDER BY u.name",
        (company["id"],),
    )


@router.post("/members", status_code=201)
def add_member(body: MemberRequest, company: Owner):
    users = store.rows("SELECT id FROM users WHERE email=?", (body.email,))
    if not users:
        raise HTTPException(
            404, "Ask this teammate to create a ForeSight account first, then add their email here."
        )
    user_id = users[0]["id"]
    with store.connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        if connection.execute(
            "SELECT 1 FROM memberships WHERE user_id=? AND company_id=?", (user_id, company["id"])
        ).fetchone():
            raise HTTPException(
                409,
                "This account is already a member. Remove access before adding a different role.",
            )
        connection.execute(
            "INSERT INTO memberships VALUES (?,?,?)", (user_id, company["id"], body.role)
        )
        store.activity(
            company["id"], "access", "Team member added", f"{body.email} · {body.role}", connection
        )
    return {"id": user_id, "role": body.role}


@router.delete("/members/{user_id}", status_code=204)
def remove_member(user_id: str, company: Owner):
    with store.connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        target = connection.execute(
            "SELECT role FROM memberships WHERE user_id=? AND company_id=?",
            (user_id, company["id"]),
        ).fetchone()
        if not target:
            raise HTTPException(404, "Company member not found")
        owners = connection.execute(
            "SELECT COUNT(*) FROM memberships WHERE company_id=? AND role='owner'", (company["id"],)
        ).fetchone()[0]
        if target["role"] == "owner" and owners <= 1:
            raise HTTPException(409, "A company must retain at least one owner.")
        connection.execute(
            "DELETE FROM memberships WHERE user_id=? AND company_id=?", (user_id, company["id"])
        )
        store.activity(
            company["id"], "access", "Team access removed", "Membership revoked", connection
        )


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
