import hashlib
import json
import os
import secrets
import sqlite3
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime, timedelta

from decisioniq.config import ROOT, configured_path

_snapshot_connection = ContextVar("dashboard_snapshot_connection", default=None)

SCHEMA = """
CREATE TABLE IF NOT EXISTS config (name TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS companies (id TEXT PRIMARY KEY, name TEXT NOT NULL, config TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sales (
 company_id TEXT NOT NULL REFERENCES companies(id), record_id TEXT NOT NULL,
 date TEXT NOT NULL, product_id TEXT NOT NULL, product TEXT NOT NULL,
 units REAL, sales REAL NOT NULL, currency TEXT NOT NULL, batch_id TEXT NOT NULL,
 PRIMARY KEY (company_id, record_id));
CREATE INDEX IF NOT EXISTS sales_company_date ON sales(company_id,date);
CREATE TABLE IF NOT EXISTS batches (
 id TEXT PRIMARY KEY, company_id TEXT NOT NULL REFERENCES companies(id), name TEXT NOT NULL,
 source TEXT NOT NULL, kind TEXT NOT NULL, status TEXT NOT NULL, received_at TEXT NOT NULL,
 processed_at TEXT, raw TEXT NOT NULL, options TEXT NOT NULL, result TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS forecasts (company_id TEXT PRIMARY KEY REFERENCES companies(id), value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS events (
 id TEXT PRIMARY KEY, company_id TEXT NOT NULL REFERENCES companies(id), kind TEXT NOT NULL,
 occurred_at TEXT NOT NULL, payload TEXT NOT NULL, result TEXT NOT NULL,
 UNIQUE(company_id,kind,id));
CREATE TABLE IF NOT EXISTS activity (
 id TEXT PRIMARY KEY, company_id TEXT NOT NULL REFERENCES companies(id), kind TEXT NOT NULL,
 title TEXT NOT NULL, detail TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS reminders (
 id TEXT PRIMARY KEY, company_id TEXT NOT NULL REFERENCES companies(id), action TEXT NOT NULL,
 title TEXT NOT NULL, detail TEXT NOT NULL, created_at TEXT NOT NULL, read_at TEXT,
 resolved_at TEXT, due_key TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS api_keys (
 hash TEXT PRIMARY KEY, company_id TEXT NOT NULL REFERENCES companies(id), prefix TEXT NOT NULL,
 created_at TEXT NOT NULL);
"""


def now():
    return datetime.now(UTC)


def stamp():
    return now().isoformat()


def uid():
    return uuid.uuid4().hex


@contextmanager
def connect():
    shared = _snapshot_connection.get()
    if shared is not None:
        yield shared
        return
    path = configured_path("DECISIONIQ_DB_PATH", "data/dashboard.sqlite3")
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=20)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


@contextmanager
def snapshot():
    """Keep a dashboard response consistent while ingestion commits concurrently."""
    with connect() as connection:
        connection.execute("BEGIN")
        marker = _snapshot_connection.set(connection)
        try:
            yield connection
        finally:
            _snapshot_connection.reset(marker)


def rows(query, parameters=()):
    with connect() as connection:
        return [dict(row) for row in connection.execute(query, parameters).fetchall()]


def company(company_id):
    result = rows("SELECT * FROM companies WHERE id=?", (company_id,))
    if not result:
        raise ValueError("Unknown company workspace")
    value = result[0]
    return {"id": value["id"], "name": value["name"], **json.loads(value["config"])}


def update_company(company_id, **values):
    with connect() as connection:
        row = connection.execute(
            "SELECT config FROM companies WHERE id=?", (company_id,)
        ).fetchone()
        if row is None:
            raise ValueError("Unknown company workspace")
        config = json.loads(row["config"])
        config.update(values)
        connection.execute(
            "UPDATE companies SET config=? WHERE id=?", (json.dumps(config), company_id)
        )
    return company(company_id)


def activity(company_id, kind, title, detail="", connection=None):
    parameters = (uid(), company_id, kind, title, detail, stamp())
    query = "INSERT INTO activity VALUES (?,?,?,?,?,?)"
    if connection is not None:
        connection.execute(query, parameters)
    else:
        with connect() as connection:
            connection.execute(query, parameters)


def initialize():
    with connect() as connection:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.executescript(SCHEMA)
        connection.execute(
            "INSERT OR IGNORE INTO config VALUES ('session_secret',?)", (secrets.token_hex(32),)
        )
        if connection.execute("SELECT 1 FROM companies LIMIT 1").fetchone():
            migrate_public_sales(connection)
            return
        from zoneinfo import ZoneInfo

        today = now().astimezone(ZoneInfo("Asia/Kolkata")).date()
        for company_id, name, segment, state, initials in [
            ("aster", "Aster Trading", "United Kingdom", "active", "AT"),
            ("maison", "Maison Supply", "France", "paused", "MS"),
            ("nordhaus", "Nordhaus", "Germany", "upload_only", "NH"),
        ]:
            config = {
                "initials": initials,
                "segment": segment,
                "currency": "GBP",
                "source": "UCI Online Retail",
                "source_url": "https://doi.org/10.24432/C5BW33",
                "source_kind": "public",
                "sales_basis": "net_recorded_sales",
                "description": f"Fictional sample workspace · {segment} customer segment",
                "api_state": state,
                "calendar_complete": True,
                "timezone": "Asia/Kolkata",
                "expected_period_end": str(today - timedelta(days=1)),
                "next_due": (
                    now() + timedelta(days=1) if state == "active" else now() - timedelta(days=2)
                ).isoformat(),
                "reminder_hours": 24,
                "snoozed_until": None,
            }
            connection.execute(
                "INSERT INTO companies VALUES (?,?,?)", (company_id, name, json.dumps(config))
            )
        migrate_public_sales(connection)
        for company_id in ["aster", "maison", "nordhaus"]:
            count = connection.execute(
                "SELECT COUNT(*) FROM sales WHERE company_id=?", (company_id,)
            ).fetchone()[0]
            activity(
                company_id,
                "data",
                "Public sales history imported",
                f"{count:,} daily product observations · GBP · 2010–2011",
                connection,
            )
    path = configured_path("DECISIONIQ_DB_PATH", "data/dashboard.sqlite3")
    os.chmod(path, 0o600)
    seed_security()


def seed_security():
    from services.anomaly.predict import predict_login
    from decisioniq.errors import ModelUnavailable

    profiles = [
        (10, 0, 0, 5, 0),
        (14, 0, 0, 6, 0),
        (9, 1, 0, 4, 0),
        (3, 10, 1, 1, 1),
        (12, 0, 0, 5, 0),
        (23, 25, 1, 0, 1),
        (11, 0, 0, 7, 0),
        (2, 8, 1, 1, 1),
    ]
    for company_id in ["aster", "maison", "nordhaus"]:
        with connect() as connection:
            for index, profile in enumerate(profiles):
                payload = dict(
                    zip(
                        [
                            "login_hour",
                            "failed_attempts",
                            "new_device",
                            "login_frequency",
                            "location_difference",
                        ],
                        profile,
                    )
                )
                payload["source"] = "Synthetic login demonstration"
                payload["actor"] = f"Sample user {index + 1:02d}"
                try:
                    result = predict_login(
                        {k: v for k, v in payload.items() if k not in {"source", "actor"}}
                    )
                    result["status"] = "available"
                except ModelUnavailable:
                    result = {"status": "unavailable"}
                connection.execute(
                    "INSERT OR IGNORE INTO events VALUES (?,?,?,?,?,?)",
                    (
                        f"sample-{company_id}-{index}",
                        company_id,
                        "login",
                        (now() - timedelta(hours=index * 3 + 1)).isoformat(),
                        json.dumps(payload),
                        json.dumps(result),
                    ),
                )


def issue_key(company_id):
    value = "diq_" + secrets.token_urlsafe(32)
    digest = hashlib.sha256(value.encode()).hexdigest()
    with connect() as connection:
        connection.execute("DELETE FROM api_keys WHERE company_id=?", (company_id,))
        connection.execute(
            "INSERT INTO api_keys VALUES (?,?,?,?)", (digest, company_id, value[:10], stamp())
        )
    activity(
        company_id, "integration", "API credential rotated", "The previous credential was revoked."
    )
    return value


def migrate_public_sales(connection):
    import csv

    version = connection.execute(
        "SELECT value FROM config WHERE name='demo_data_version'"
    ).fetchone()
    if version and version["value"] == "3":
        return
    connection.execute(
        "DELETE FROM sales WHERE batch_id='uci-seed' AND company_id IN ('aster','maison','nordhaus')"
    )
    connection.execute("DELETE FROM forecasts WHERE company_id IN ('aster','maison','nordhaus')")
    with (ROOT / "services/finance/data/demo_sales.csv").open() as handle:
        for row in csv.DictReader(handle):
            connection.execute(
                "INSERT INTO sales VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    row["company_id"],
                    f"uci:{row['date']}:{row['product_id']}",
                    row["date"],
                    row["product_id"],
                    row["product"],
                    float(row["units"]),
                    float(row["sales"]),
                    "GBP",
                    "uci-seed",
                ),
            )
    for company_id in ["aster", "maison", "nordhaus"]:
        record = connection.execute(
            "SELECT config FROM companies WHERE id=?", (company_id,)
        ).fetchone()
        if record:
            config = json.loads(record["config"])
            config["sales_basis"] = "net_recorded_sales"
            connection.execute(
                "UPDATE companies SET config=? WHERE id=?", (json.dumps(config), company_id)
            )
    connection.execute(
        "INSERT INTO config VALUES ('demo_data_version','3') ON CONFLICT(name) DO UPDATE SET value='3'"
    )
