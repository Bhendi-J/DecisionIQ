import csv
import io
import json
from datetime import date, timedelta
from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

from decisioniq.dashboard import analytics, ingestion, store
from decisioniq.dashboard.auth import (
    User,
    account_view,
    current_company,
    intake_company,
    owner_company,
)
from decisioniq.dashboard.reminders import evaluate_reminders
from decisioniq.errors import ModelUnavailable
from services.anomaly.api import LoginData
from services.anomaly.predict import predict_login
from services.phishing.api import EmailData
from services.phishing.predict import detect_phishing
from services.phishing.eml_parser import parse_eml_bytes

router = APIRouter(prefix="/api", tags=["Dashboard"])
Company = Annotated[dict, Depends(current_company)]
Owner = Annotated[dict, Depends(owner_company)]
Intake = Annotated[dict, Depends(intake_company)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class NewCompany(StrictModel):
    name: str = Field(min_length=2, max_length=50)
    currency: str = "GBP"
    timezone: str = "Asia/Kolkata"

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value):
        if len(value.strip()) < 2:
            raise ValueError("Enter a workspace name")
        return value.strip()

    @field_validator("currency")
    @classmethod
    def supported_currency(cls, value):
        if value not in ingestion.CURRENCIES:
            raise ValueError("Select a supported currency")
        return value

    @field_validator("timezone")
    @classmethod
    def supported_zone(cls, value):
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError:
            raise ValueError("Use a valid IANA time zone") from None
        return value


class MappingOptions(StrictModel):
    mapping: dict[str, str]
    currency: str
    calendar_complete: bool = False
    date_format: Literal["iso", "day_first", "month_first"] = "iso"
    number_format: Literal["decimal_point", "decimal_comma"] = "decimal_point"

    @field_validator("mapping")
    @classmethod
    def allowed_mapping(cls, value):
        if not set(value).issubset(ingestion.ALIASES) or any(
            len(column) > 100 for column in value.values()
        ):
            raise ValueError("Use supported sales mapping fields")
        return value


class Policy(StrictModel):
    api_state: str | None = None
    next_due: AwareDatetime | None = None
    expected_period_end: date | None = None
    reminder_hours: int | None = Field(None, ge=1, le=168)
    calendar_complete: bool | None = None

    @field_validator("api_state")
    @classmethod
    def state_allowed(cls, value):
        if value not in {None, "active", "paused", "upload_only"}:
            raise ValueError("Unsupported intake state")
        return value


class Snooze(StrictModel):
    hours: int = Field(24, ge=1, le=168)


class SalesIntake(StrictModel):
    records: list[dict] = Field(min_length=1, max_length=ingestion.MAX_ROWS)
    currency: str
    calendar_complete: bool = False
    mapping: dict[str, str] | None = None
    name: str = Field("API sales batch", max_length=100)

    @field_validator("records")
    @classmethod
    def flat_records(cls, value):
        if any(
            len(row) > 100
            or any(
                not isinstance(key, str)
                or len(key) > 100
                or isinstance(cell, (dict, list))
                or (isinstance(cell, str) and len(cell) > 5000)
                for key, cell in row.items()
            )
            for row in value
        ):
            raise ValueError(
                "Use flat records with at most 100 fields and cells no longer than 5,000 characters"
            )
        return value


class LoginEvent(LoginData):
    event_id: str = Field(min_length=1, max_length=100)
    occurred_at: AwareDatetime
    actor: str = Field("Integration event", max_length=100)


def writable_sales(company):
    if company["source_kind"] == "public":
        raise HTTPException(
            409,
            "This public dataset is read-only. Create an upload workspace to analyze your own data separately.",
        )


@router.get("/bootstrap")
def bootstrap(user: User):
    return account_view(user)


@router.get("/dashboard")
def get_dashboard(company: Company, horizon: int = 30):
    if horizon not in {30, 60, 90}:
        raise HTTPException(422, "Choose a 30, 60, or 90 day outlook")
    with store.snapshot():
        value = analytics.dashboard(company["id"], horizon)
    value["company"]["role"] = company["role"]
    from services.phishing.predict import _load_bundle

    try:
        _load_bundle()
        value["phishing_status"] = "ready"
    except ModelUnavailable:
        value["phishing_status"] = "model_required"
    return value


@router.post("/companies", status_code=201)
def new_workspace(body: NewCompany, user: User):
    with store.connect() as connection:
        company_id = store.create_workspace(body.name, body.currency, body.timezone, connection)
        connection.execute(
            "INSERT INTO memberships VALUES (?,?,'owner')", (user["user_id"], company_id)
        )
        connection.execute(
            "UPDATE sessions SET company_id=? WHERE token_hash=?", (company_id, user["token_hash"])
        )
    return {**store.company(company_id), "role": "admin" if user["is_admin"] else "owner"}


@router.patch("/settings")
def settings(body: Policy, company: Owner, background_tasks: BackgroundTasks):
    values = body.model_dump(exclude_none=True, mode="json")
    result = store.update_company(company["id"], **values)
    store.activity(
        company["id"],
        "settings",
        "Data policy updated",
        ", ".join(key.replace("_", " ") for key in values),
    )
    if body.calendar_complete is not None:
        background_tasks.add_task(analytics.refresh_forecast, company["id"])
    evaluate_reminders()
    return result


@router.post("/settings/api-key")
def rotate_key(company: Owner):
    return {
        "key": store.issue_key(company["id"]),
        "message": "Copy this key now. Only its hash is stored; rotating it revokes the previous key.",
    }


@router.post("/uploads", status_code=201)
async def upload(company: Company, file: UploadFile = File(...)):
    writable_sales(company)
    content = await file.read(5 * 1024 * 1024 + 1)
    _, records = ingestion.read_upload(content, file.filename or "upload.csv")
    batch_id = ingestion.create_batch(company["id"], file.filename or "Sales upload", records)
    evaluate_reminders()
    return ingestion.get_batch(company["id"], batch_id)


@router.get("/batches/{batch_id}")
def batch_detail(batch_id: str, company: Company):
    return ingestion.get_batch(company["id"], batch_id)


@router.post("/batches/{batch_id}/validate")
def validate(batch_id: str, body: MappingOptions, company: Company):
    batch = ingestion.get_batch(company["id"], batch_id)
    if batch["status"] in {"processing", "processed"}:
        raise HTTPException(409, "This batch has already been submitted for processing.")
    _, result = ingestion.validate_batch(company, batch_id, body.model_dump())
    with store.connect() as connection:
        connection.execute(
            "UPDATE batches SET options=?,status=?,result=? WHERE company_id=? AND id=?",
            (
                body.model_dump_json(),
                "ready" if not result["error_count"] else "needs_mapping",
                json.dumps(result),
                company["id"],
                batch_id,
            ),
        )
    return result


@router.post("/batches/{batch_id}/process", status_code=202)
def process(batch_id: str, company: Company, background_tasks: BackgroundTasks):
    with store.connect() as connection:
        result = connection.execute(
            "UPDATE batches SET status='processing' WHERE company_id=? AND id=? AND status='ready'",
            (company["id"], batch_id),
        )
        if result.rowcount != 1:
            raise HTTPException(
                409,
                "Validate this batch successfully before processing; already submitted batches are not processed twice.",
            )
    background_tasks.add_task(ingestion.process_batch, company["id"], batch_id)
    return {"status": "processing", "batch_id": batch_id}


@router.delete("/batches/{batch_id}", status_code=204)
def discard_batch(batch_id: str, company: Company):
    with store.connect() as connection:
        result = connection.execute(
            "DELETE FROM batches WHERE company_id=? AND id=? AND status IN ('needs_mapping','ready','failed')",
            (company["id"], batch_id),
        )
        if result.rowcount != 1:
            raise HTTPException(
                409, "Only an unprocessed batch in this workspace can be discarded."
            )
        store.activity(company["id"], "upload", "Unprocessed batch discarded", "", connection)
    evaluate_reminders()


@router.post("/intake/sales", status_code=202)
def intake_sales(body: SalesIntake, company: Intake, background_tasks: BackgroundTasks):
    writable_sales(company)
    if len(body.model_dump_json()) > 5 * 1024 * 1024:
        raise HTTPException(413, "Use sales batches no larger than 5 MB")
    columns = list(dict.fromkeys(key for row in body.records[:100] for key in row))
    options = {
        "mapping": body.mapping or ingestion.suggestions(columns),
        "currency": body.currency,
        "calendar_complete": body.calendar_complete,
    }
    id_column = options["mapping"].get("record_id")
    if not id_column or any(row.get(id_column) in {None, ""} for row in body.records):
        raise HTTPException(422, "API records require stable record IDs for retry-safe ingestion.")
    batch_id = ingestion.create_batch(company["id"], body.name, body.records, "api", options)
    _, validation = ingestion.validate_batch(company, batch_id, options)
    if validation["error_count"]:
        with store.connect() as connection:
            connection.execute(
                "UPDATE batches SET status='failed',result=? WHERE id=?",
                (json.dumps(validation), batch_id),
            )
        raise HTTPException(422, validation)
    with store.connect() as connection:
        connection.execute("UPDATE batches SET status='processing' WHERE id=?", (batch_id,))
    background_tasks.add_task(ingestion.process_batch, company["id"], batch_id)
    return {"status": "processing", "batch_id": batch_id}


@router.post("/intake/logins", status_code=201)
def intake_login(body: LoginEvent, company: Intake):
    payload = body.model_dump(mode="json")
    event_id = f"api:{company['id']}:{body.event_id}"
    previous = store.rows(
        "SELECT payload,result FROM events WHERE company_id=? AND id=?", (company["id"], event_id)
    )
    if previous:
        if json.loads(previous[0]["payload"]) != {**payload, "source": "Company API"}:
            raise HTTPException(409, "This event ID already exists with different data")
        return {"status": "duplicate", "result": json.loads(previous[0]["result"])}
    features = {key: payload[key] for key in LoginData.model_fields}
    result = {**predict_login(features), "status": "available"}
    with store.connect() as connection:
        connection.execute(
            "INSERT INTO events VALUES (?,?,?,?,?,?)",
            (
                event_id,
                company["id"],
                "login",
                body.occurred_at.isoformat(),
                json.dumps({**payload, "source": "Company API"}),
                json.dumps(result),
            ),
        )
        store.activity(
            company["id"],
            "security",
            "Login event analyzed",
            "Anomaly detected" if result["is_anomaly"] else "No anomaly detected",
            connection,
        )
    return {"status": "accepted", "result": result}


@router.post("/security/login")
def analyze_login(body: LoginData, company: Company):
    result = {**predict_login(body.model_dump()), "status": "available"}
    with store.connect() as connection:
        connection.execute(
            "INSERT INTO events VALUES (?,?,?,?,?,?)",
            (
                store.uid(),
                company["id"],
                "login",
                store.stamp(),
                json.dumps(
                    {
                        **body.model_dump(),
                        "source": "Manual demonstration",
                        "actor": "Manual analysis",
                    }
                ),
                json.dumps(result),
            ),
        )
        store.activity(
            company["id"],
            "security",
            "Login example analyzed",
            "Anomaly detected" if result["is_anomaly"] else "No anomaly detected",
            connection,
        )
    return result


@router.post("/security/email")
def analyze_email(body: EmailData, company: Company):
    result = detect_phishing(body.text)
    with store.connect() as connection:
        # Keep the result and text length, rather than retaining raw email contents.
        connection.execute(
            "INSERT INTO events VALUES (?,?,?,?,?,?)",
            (
                store.uid(),
                company["id"],
                "email",
                store.stamp(),
                json.dumps({"characters": len(body.text), "source": "Manual analysis"}),
                json.dumps({**result, "status": "available"}),
            ),
        )
        store.activity(
            company["id"],
            "security",
            "Email example analyzed",
            "Phishing detected" if result["is_phishing"] else "No phishing detected",
            connection,
        )
    return result


@router.post("/security/email/upload")
async def analyze_email_file(file: UploadFile, company: Company):
    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(400, "Email file size exceeds 10MB limit.")
    try:
        parsed = parse_eml_bytes(contents)
    except Exception as exc:
        raise HTTPException(400, f"Could not parse email file: {exc}")

    # Use extracted subject and body for classification
    text_to_analyze = f"Subject: {parsed['subject']}\n\n{parsed['full_body']}".strip()
    if not text_to_analyze:
        text_to_analyze = parsed['subject'] or "No content"

    result = detect_phishing(text_to_analyze)

    # Calculate overall risk score factoring in headers
    # E.g., if model says safe but SPF failed or display name spoofed, flag high risk
    header_flags = []
    if parsed["spf"] == "fail":
        header_flags.append("SPF verification failed (sending IP not authorized)")
    if parsed["dkim"] == "fail":
        header_flags.append("DKIM signature verification failed")
    if parsed["dmarc"] == "fail":
        header_flags.append("DMARC alignment check failed")
    if parsed["name_spoof"]:
        header_flags.append("Display name brand spoofing detected")
    if parsed["suspicious_links"]:
        header_flags.append(f"{len(parsed['suspicious_links'])} deceptive hyperlink(s) detected")

    adjusted_risk_score = result["risk_score"]
    if header_flags:
        adjusted_risk_score = max(adjusted_risk_score, 85 if parsed["name_spoof"] or parsed["suspicious_links"] else 70)
    is_phishing_overall = result["is_phishing"] or bool(header_flags)

    response_data = {
        **result,
        "is_phishing": is_phishing_overall,
        "risk_score": adjusted_risk_score,
        "parsed_metadata": {
            "subject": parsed["subject"],
            "from": parsed["from"],
            "reply_to": parsed["reply_to"],
            "date": parsed["date"],
            "spf": parsed["spf"],
            "dkim": parsed["dkim"],
            "dmarc": parsed["dmarc"],
            "name_spoof": parsed["name_spoof"],
            "suspicious_links": parsed["suspicious_links"],
            "attachments": parsed["attachments"],
            "body_preview": parsed["body_preview"],
            "header_flags": header_flags,
        },
    }

    with store.connect() as connection:
        connection.execute(
            "INSERT INTO events VALUES (?,?,?,?,?,?)",
            (
                store.uid(),
                company["id"],
                "email",
                store.stamp(),
                json.dumps({
                    "filename": file.filename,
                    "characters": len(text_to_analyze),
                    "source": ".eml file upload",
                    "subject": parsed["subject"][:60],
                }),
                json.dumps({**response_data, "status": "available"}),
            ),
        )
        store.activity(
            company["id"],
            "security",
            f"Email file analyzed: {file.filename}",
            "Phishing detected" if is_phishing_overall else "No phishing detected",
            connection,
        )

    return response_data


@router.post("/reminders/snooze")
def snooze(body: Snooze, company: Company):
    until = (store.now() + timedelta(hours=body.hours)).isoformat()
    store.update_company(company["id"], snoozed_until=until)
    store.activity(company["id"], "reminder", "Data reminders snoozed", f"For {body.hours} hours")
    return {"snoozed_until": until}


@router.delete("/reminders/snooze")
def resume_reminders(company: Company):
    store.update_company(company["id"], snoozed_until=None)
    store.activity(company["id"], "reminder", "Data reminders resumed")
    evaluate_reminders()
    return {"snoozed_until": None}


@router.post("/reminders/{reminder_id}/read")
def mark_read(reminder_id: str, company: Company):
    with store.connect() as connection:
        result = connection.execute(
            "UPDATE reminders SET read_at=? WHERE id=? AND company_id=?",
            (store.stamp(), reminder_id, company["id"]),
        )
        if not result.rowcount:
            raise HTTPException(404, "Reminder not found")
    return {"read": True}


@router.get("/export/sales.csv")
def export_sales(company: Company):
    records = store.rows(
        "SELECT record_id,date,product_id,product,units,sales,currency FROM sales WHERE company_id=? ORDER BY date,product_id",
        (company["id"],),
    )
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "record_id",
            "date",
            "product_id",
            "product",
            "units",
            "sales",
            "currency",
            "source",
            "source_url",
        ]
    )
    for record in records:
        writer.writerow(
            [
                ("'" + value)
                if isinstance(value, str) and value.startswith(("=", "+", "-", "@"))
                else value
                for value in [*record.values(), company["source"], company.get("source_url") or ""]
            ]
        )
    return PlainTextResponse(
        output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{company["id"]}-sales.csv"'},
    )


@router.get("/upload-template.csv")
def template(company: Company):
    return PlainTextResponse(
        "record_id,date,product_id,product,units,sales,currency\nexample-001,2026-10-01,SKU-001,Example product,3,150.00,"
        + company["currency"]
        + "\n",
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="foresight-sales-template.csv"'},
    )
