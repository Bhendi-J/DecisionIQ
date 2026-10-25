"""Verify intake, isolation, data meaning, and reminder behavior through the API."""

import csv
import io
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from decisioniq.dashboard import store
from decisioniq.dashboard.reminders import evaluate_reminders
from decisioniq.main import app


@pytest.fixture(scope="module")
def dashboard_client(tmp_path_factory):
    import os

    old = os.environ.get("DECISIONIQ_DB_PATH")
    os.environ["DECISIONIQ_DB_PATH"] = str(tmp_path_factory.mktemp("dashboard") / "store.sqlite3")
    with TestClient(app) as client:
        assert client.post("/api/demo/session", json={"company_id": "aster"}).status_code == 200
        yield client
    if old is None:
        os.environ.pop("DECISIONIQ_DB_PATH", None)
    else:
        os.environ["DECISIONIQ_DB_PATH"] = old


def new_company(client, name="Test workspace"):
    result = client.post("/api/companies", json={"name": name, "currency": "GBP"})
    assert result.status_code == 201, result.text
    return result.json()


def csv_file(records):
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(records[0]))
    writer.writeheader()
    writer.writerows(records)
    return output.getvalue().encode()


def test_public_sources_are_distinct_and_do_not_claim_cash_flow(dashboard_client):
    client = dashboard_client
    totals = []
    for company_id in ["aster", "maison", "nordhaus"]:
        client.post("/api/demo/session", json={"company_id": company_id})
        data = client.get("/api/dashboard").json()
        assert data["company"]["currency"] == "GBP"
        assert data["company"]["sales_basis"] == "net_recorded_sales"
        assert data["data_end"] <= "2011-12-09"
        assert len(data["forecast"]["future"]) == 30
        assert len(data["forecast"]["backtest"]) == 28
        assert data["forecast"]["mae"] <= data["forecast"]["baseline_mae"]
        assert all(item["product_id"][0].isdigit() for item in data["products"])
        assert data["narration"]["external_processing"] is False
        assert "cash_balance" not in data["metrics"]
        totals.append(data["metrics"]["sales_30d"])
        assert (
            client.post(
                "/api/uploads", files={"file": ("file.csv", b"date,sales\n2026-01-01,10")}
            ).status_code
            == 409
        )
    assert len(set(totals)) == 3


def test_sessions_cannot_be_forged(dashboard_client):
    client = dashboard_client
    original = client.cookies.get("decisioniq_session")
    client.cookies.clear()
    assert client.get("/api/dashboard").status_code == 401
    client.cookies.set("decisioniq_session", "forged.signature")
    assert client.get("/api/dashboard").status_code == 401
    client.cookies.clear()
    client.cookies.set("decisioniq_session", original)


def test_upload_mapping_processing_and_cross_company_isolation(dashboard_client):
    client = dashboard_client
    company = new_company(client)
    records = [
        {
            "sale_id": "invoice-a",
            "sold_on": "2026-01-01",
            "item": "Notebook",
            "amount": 120,
            "quantity": 3,
        },
        {
            "sale_id": "invoice-b",
            "sold_on": "2026-01-02",
            "item": "Notebook",
            "amount": -40,
            "quantity": -1,
        },
    ]
    response = client.post(
        "/api/uploads", files={"file": ("sales.csv", csv_file(records), "text/csv")}
    )
    assert response.status_code == 201, response.text
    batch_id = response.json()["id"]
    assert response.json()["row_count"] == 2
    mapping = {
        "record_id": "sale_id",
        "date": "sold_on",
        "sales": "amount",
        "product": "item",
        "units": "quantity",
    }
    validation = client.post(
        f"/api/batches/{batch_id}/validate", json={"mapping": mapping, "currency": "GBP"}
    )
    assert validation.status_code == 200, validation.text
    assert validation.json()["error_count"] == 0
    assert client.post(f"/api/batches/{batch_id}/process").status_code == 202
    result = client.get("/api/dashboard").json()
    assert sum(row["sales"] for row in result["historical"]) == 80
    assert result["forecast"]["status"] == "insufficient"
    assert result["products"][0]["units"] == 2
    assert client.post(f"/api/batches/{batch_id}/process").status_code == 409
    other = new_company(client, "Other tenant")
    assert other["id"] != company["id"]
    assert client.get(f"/api/batches/{batch_id}").status_code == 404
    assert client.get("/api/dashboard").json()["historical"] == []


def test_api_key_scope_pause_and_retry_deduplication(dashboard_client):
    client = dashboard_client
    company = new_company(client, "API workspace")
    key = client.post("/api/settings/api-key").json()["key"]
    payload = {
        "currency": "GBP",
        "records": [
            {"record_id": "order-001", "date": "2026-01-10", "sales": 400, "product": "Notebook"}
        ],
    }
    assert client.post("/api/intake/sales", json=payload).status_code == 401
    assert (
        client.post("/api/intake/sales", json=payload, headers={"X-API-Key": key}).status_code
        == 409
    )
    client.patch("/api/settings", json={"api_state": "active"})
    response = client.post("/api/intake/sales", json=payload, headers={"X-API-Key": key})
    assert response.status_code == 202, response.text
    assert (
        client.post("/api/intake/sales", json=payload, headers={"X-API-Key": key}).status_code
        == 202
    )
    batches = client.get("/api/dashboard").json()["batches"]
    assert sum(item["result"].get("inserted", 0) for item in batches) == 1
    assert sum(item["result"].get("duplicates", 0) for item in batches) == 1
    # The authenticated key determines the tenant, regardless of the current dashboard session.
    new_company(client, "Unrelated dashboard session")
    payload["records"][0] = {"record_id": "order-002", "date": "2026-01-11", "sales": 200}
    assert (
        client.post("/api/intake/sales", json=payload, headers={"X-API-Key": key}).status_code
        == 202
    )
    assert client.get("/api/dashboard").json()["historical"] == []
    client.post("/api/demo/session", json={"company_id": company["id"]})
    assert sum(row["sales"] for row in client.get("/api/dashboard").json()["historical"]) == 600
    client.patch("/api/settings", json={"api_state": "paused"})
    assert (
        client.post("/api/intake/sales", json=payload, headers={"X-API-Key": key}).status_code
        == 409
    )
    rotated = client.post("/api/settings/api-key").json()["key"]
    assert rotated != key
    assert (
        client.post("/api/intake/sales", json=payload, headers={"X-API-Key": key}).status_code
        == 401
    )
    stored = store.rows("SELECT hash,prefix FROM api_keys WHERE company_id=?", (company["id"],))[0]
    assert stored["hash"] != rotated and len(stored["hash"]) == 64


def test_invalid_currency_and_missing_values_do_not_become_financial_facts(dashboard_client):
    client = dashboard_client
    new_company(client, "Incomplete data")
    response = client.post(
        "/api/uploads", files={"file": ("missing.csv", b"date,sales\n2026-01-01,\n")}
    )
    batch = response.json()["id"]
    validation = client.post(
        f"/api/batches/{batch}/validate",
        json={"mapping": {"date": "date", "sales": "sales"}, "currency": "GBP"},
    )
    assert validation.json()["error_count"] == 1
    assert "missing" in validation.json()["errors"][0]["message"]
    assert client.post(f"/api/batches/{batch}/process").status_code == 409
    assert (
        client.post(
            f"/api/batches/{batch}/validate",
            json={"mapping": {"date": "date", "sales": "sales"}, "currency": "USD"},
        ).status_code
        == 422
    )
    assert client.get("/api/dashboard").json()["metrics"]["units_30d"] is None


def test_reminders_obey_intake_coverage_snooze_and_processing_state(dashboard_client):
    client = dashboard_client
    company = new_company(client, "Reminder scope")
    at = store.now()
    store.update_company(
        company["id"],
        api_state="active",
        next_due=(at - timedelta(days=1)).isoformat(),
        expected_period_end="2026-01-01",
    )
    evaluate_reminders(at)
    assert not store.rows(
        "SELECT * FROM reminders WHERE company_id=? AND resolved_at IS NULL", (company["id"],)
    )
    store.update_company(company["id"], api_state="paused")
    evaluate_reminders(at)
    reminders = store.rows(
        "SELECT * FROM reminders WHERE company_id=? AND resolved_at IS NULL", (company["id"],)
    )
    assert len(reminders) == 1 and reminders[0]["action"] == "upload"
    evaluate_reminders(at + timedelta(minutes=5))
    assert len(store.rows("SELECT * FROM reminders WHERE company_id=?", (company["id"],))) == 1
    assert client.post("/api/reminders/snooze", json={"hours": 24}).status_code == 200
    evaluate_reminders(at + timedelta(hours=2))
    assert len(store.rows("SELECT * FROM reminders WHERE company_id=?", (company["id"],))) == 1
    store.update_company(company["id"], api_state="upload_only", snoozed_until=None)
    upload = client.post(
        "/api/uploads",
        files={"file": ("pending.csv", b"record_id,date,sales\nreminder-1,2026-01-01,10\n")},
    )
    assert upload.status_code == 201
    batch_id = upload.json()["id"]
    pending = store.rows(
        "SELECT * FROM reminders WHERE company_id=? AND resolved_at IS NULL", (company["id"],)
    )
    assert pending[0]["action"] == "process"
    client.post(
        f"/api/batches/{batch_id}/validate",
        json={
            "mapping": {"record_id": "record_id", "date": "date", "sales": "sales"},
            "currency": "GBP",
        },
    )
    client.post(f"/api/batches/{batch_id}/process")
    evaluate_reminders()
    assert not store.rows(
        "SELECT * FROM reminders WHERE company_id=? AND resolved_at IS NULL", (company["id"],)
    )


def test_login_time_api_events_use_company_credentials_and_stable_ids(dashboard_client):
    client = dashboard_client
    new_company(client, "Login integration")
    key = client.post("/api/settings/api-key").json()["key"]
    client.patch("/api/settings", json={"api_state": "active"})
    event = {
        "event_id": "login-001",
        "occurred_at": store.stamp(),
        "login_hour": 3,
        "failed_attempts": 8,
        "new_device": 1,
        "login_frequency": 1,
        "location_difference": 1,
    }
    response = client.post("/api/intake/logins", json=event, headers={"X-API-Key": key})
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "accepted"
    assert (
        client.post("/api/intake/logins", json=event, headers={"X-API-Key": key}).json()["status"]
        == "duplicate"
    )
    assert client.get("/api/dashboard").json()["metrics"]["login_events"] == 1


def test_xlsx_upload_and_unsupported_formats(dashboard_client):
    from openpyxl import Workbook

    client = dashboard_client
    new_company(client, "Spreadsheet imports")
    workbook = Workbook()
    workbook.active.append(["date", "sales"])
    workbook.active.append(["2026-01-01", 123.45])
    output = io.BytesIO()
    workbook.save(output)
    assert (
        client.post("/api/uploads", files={"file": ("sales.xlsx", output.getvalue())}).status_code
        == 201
    )
    assert (
        client.post(
            "/api/uploads", files={"file": ("statement.pdf", b"not-a-spreadsheet")}
        ).status_code
        == 415
    )


def test_date_and_decimal_conventions_are_explicit(dashboard_client):
    client = dashboard_client
    new_company(client, "Locale conventions")
    content = "date;sales;product\n01/02/2026;1.234,56;Notebook\n"
    batch = client.post("/api/uploads", files={"file": ("locale.csv", content.encode())}).json()[
        "id"
    ]
    options = {
        "mapping": {"date": "date", "sales": "sales", "product": "product"},
        "currency": "GBP",
    }
    invalid = client.post(f"/api/batches/{batch}/validate", json=options).json()
    assert invalid["error_count"] == 1
    valid = client.post(
        f"/api/batches/{batch}/validate",
        json={**options, "date_format": "day_first", "number_format": "decimal_comma"},
    ).json()
    assert valid["error_count"] == 0
    assert valid["preview"][0]["date"] == "2026-02-01"
    assert valid["preview"][0]["sales"] == 1234.56
    # A decimal comma must never silently become a thousands separator.
    from decisioniq.dashboard.ingestion import numeric

    with pytest.raises(ValueError, match="ambiguous"):
        numeric("1,23", "sales")
    assert numeric("1,23", "sales", "decimal_comma") == 1.23


def test_product_names_without_codes_remain_distinct(dashboard_client):
    client = dashboard_client
    new_company(client, "Products without SKUs")
    records = [
        {"record_id": "p1", "date": "2026-01-01", "product": "Notebook", "sales": 100},
        {"record_id": "p2", "date": "2026-01-01", "product": "Pen", "sales": 40},
    ]
    batch = client.post("/api/uploads", files={"file": ("products.csv", csv_file(records))}).json()[
        "id"
    ]
    result = client.post(
        f"/api/batches/{batch}/validate",
        json={
            "mapping": {
                "record_id": "record_id",
                "date": "date",
                "product": "product",
                "sales": "sales",
            },
            "currency": "GBP",
        },
    )
    assert result.json()["error_count"] == 0
    assert client.post(f"/api/batches/{batch}/process").status_code == 202
    products = client.get("/api/dashboard").json()["products"]
    assert len(products) == 2
    assert {p["product"] for p in products} == {"Notebook", "Pen"}
    assert all(p["units"] is None for p in products)


def test_export_reimport_preserves_record_ids_and_deduplicates(dashboard_client):
    client = dashboard_client
    new_company(client, "Export round trip")
    key = client.post("/api/settings/api-key").json()["key"]
    client.patch("/api/settings", json={"api_state": "active"})
    response = client.post(
        "/api/intake/sales",
        headers={"X-API-Key": key},
        json={
            "currency": "GBP",
            "records": [
                {"record_id": "export-1", "date": "2026-01-01", "product": "Notebook", "sales": 42}
            ],
        },
    )
    assert response.status_code == 202
    exported = client.get("/api/export/sales.csv")
    assert exported.status_code == 200
    records = list(csv.DictReader(io.StringIO(exported.text)))
    assert records[0]["record_id"] == "external:export-1"
    assert records[0]["source"] == "Company-supplied data"
    batch = client.post("/api/uploads", files={"file": ("export.csv", exported.content)}).json()[
        "id"
    ]
    validation = client.post(
        f"/api/batches/{batch}/validate",
        json={
            "currency": "GBP",
            "mapping": {
                key: key for key in ["record_id", "date", "product_id", "product", "units", "sales"]
            },
        },
    )
    assert validation.json()["error_count"] == 0
    assert client.post(f"/api/batches/{batch}/process").status_code == 202
    result = client.get(f"/api/batches/{batch}").json()["result"]
    assert result["inserted"] == 0 and result["duplicates"] == 1


def test_forecast_failure_preserves_accepted_records_and_explains_status(
    dashboard_client, monkeypatch
):
    from decisioniq.dashboard import analytics

    client = dashboard_client
    new_company(client, "Forecast failure")
    key = client.post("/api/settings/api-key").json()["key"]
    client.patch("/api/settings", json={"api_state": "active"})

    def failed_forecast(company_id):
        raise RuntimeError("Forecast preparation interrupted")

    monkeypatch.setattr(analytics, "refresh_forecast", failed_forecast)
    response = client.post(
        "/api/intake/sales",
        headers={"X-API-Key": key},
        json={
            "currency": "GBP",
            "records": [{"record_id": "saved-1", "date": "2026-01-01", "sales": 80}],
        },
    )
    assert response.status_code == 202
    batch = client.get(f"/api/batches/{response.json()['batch_id']}").json()
    assert batch["status"] == "processed" and batch["result"]["inserted"] == 1
    dashboard = client.get("/api/dashboard").json()
    assert dashboard["historical"][0]["sales"] == 80
    assert dashboard["forecast"]["status"] == "unavailable"
    assert "Sales records were saved" in dashboard["forecast"]["message"]
