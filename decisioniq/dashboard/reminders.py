"""Persistent in-app reminders; no third-party messages are sent."""

import asyncio
import logging
from datetime import datetime, timedelta

from decisioniq.dashboard import store

logger = logging.getLogger(__name__)


def evaluate_reminders(at=None):
    at = at or store.now()
    created = 0
    for entry in store.rows("SELECT id FROM companies"):
        company = store.company(entry["id"])
        pending = store.rows(
            "SELECT id,status FROM batches WHERE company_id=? AND status IN ('needs_mapping','ready','processing','failed') ORDER BY received_at DESC",
            (company["id"],),
        )
        latest = store.rows(
            "SELECT MAX(date) AS date FROM sales WHERE company_id=?", (company["id"],)
        )[0]["date"]
        due = datetime.fromisoformat(company["next_due"])
        overdue = due <= at
        covered = latest is not None and latest >= company["expected_period_end"]
        eligible = company["api_state"] in {"paused", "upload_only"}
        snoozed = (
            company.get("snoozed_until") and datetime.fromisoformat(company["snoozed_until"]) > at
        )
        action = "process" if pending else "upload"
        if pending and pending[0]["status"] == "processing":
            eligible = False
        needed = eligible and overdue and (bool(pending) or not covered)
        due_key = f"{company['expected_period_end']}:{action}"
        with store.connect() as connection:
            connection.execute(
                "UPDATE reminders SET resolved_at=? WHERE company_id=? AND resolved_at IS NULL AND (due_key!=? OR ?=0)",
                (at.isoformat(), company["id"], due_key, int(needed)),
            )
            if not needed or snoozed:
                continue
            previous = connection.execute(
                "SELECT created_at FROM reminders WHERE company_id=? AND due_key=? ORDER BY created_at DESC LIMIT 1",
                (company["id"], due_key),
            ).fetchone()
            if previous and at - datetime.fromisoformat(previous["created_at"]) < timedelta(
                hours=company["reminder_hours"]
            ):
                continue
            title = "Your uploaded data is waiting" if pending else "Your next data update is due"
            detail = (
                "Review the field mapping or process your existing batch."
                if pending
                else f"Upload data covering {company['expected_period_end']}"
                + (" or resume API intake." if company["api_state"] == "paused" else ".")
            )
            connection.execute(
                "INSERT INTO reminders VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    store.uid(),
                    company["id"],
                    action,
                    title,
                    detail,
                    at.isoformat(),
                    None,
                    None,
                    due_key,
                ),
            )
            created += 1
    return created


async def run_scheduler():
    while True:
        try:
            await asyncio.to_thread(evaluate_reminders)
        except Exception:
            logger.exception("Reminder evaluation failed")
        await asyncio.sleep(30)
