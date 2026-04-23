from __future__ import annotations

from datetime import datetime
from pathlib import Path

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler

import config
from tools import TOOL_REGISTRY
from tools.whatsapp import send_reply

Path(config.DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
_jobstore_url = f"sqlite:///{config.DATABASE_PATH}"
_scheduler = BackgroundScheduler(
    jobstores={"default": SQLAlchemyJobStore(url=_jobstore_url)}
)
_scheduler.start()


def _fire_reminder(chat_id: str, message: str) -> None:
    send_reply(chat_id, f"⏰ תזכורת: {message}")


def create_reminder(chat_id: str, remind_at_iso: str, message: str) -> str:
    """chat_id will be filled by the framework; leave empty in LLM call."""
    run_time = datetime.fromisoformat(remind_at_iso)
    job = _scheduler.add_job(
        _fire_reminder,
        "date",
        run_date=run_time,
        args=[chat_id, message],
    )
    return f"תזכורת נקבעה ל-{run_time.strftime('%d/%m %H:%M')} (מזהה: {job.id})"


def list_reminders(chat_id: str) -> str:
    """chat_id will be filled by the framework; leave empty in LLM call."""
    jobs = _scheduler.get_jobs()
    user_jobs = [j for j in jobs if j.args and j.args[0] == chat_id]
    if not user_jobs:
        return "אין תזכורות פעילות."
    lines = ["התזכורות שלך:"]
    for j in user_jobs:
        run_time = j.next_run_time
        msg = j.args[1] if len(j.args) > 1 else ""
        lines.append(f"- {run_time.strftime('%d/%m %H:%M')}: {msg} (מזהה: {j.id})")
    return "\n".join(lines)


def cancel_reminder(reminder_id: str) -> str:
    try:
        _scheduler.remove_job(reminder_id)
        return f"תזכורת {reminder_id} בוטלה."
    except Exception:
        return f"לא נמצאה תזכורת עם מזהה {reminder_id}."


TOOL_REGISTRY["create_reminder"] = {
    "schema": {
        "name": "create_reminder",
        "description": "קובעת תזכורת שתישלח ב-WhatsApp בזמן מסוים",
        "input_schema": {
            "type": "object",
            "properties": {
                "chat_id": {"type": "string", "description": "chat_id will be filled by the framework; leave empty"},
                "remind_at_iso": {"type": "string", "description": "תאריך ושעה בפורמט ISO 8601, למשל 2026-04-23T15:00:00"},
                "message": {"type": "string", "description": "תוכן התזכורת"},
            },
            "required": ["chat_id", "remind_at_iso", "message"],
        },
    },
    "fn": create_reminder,
}

TOOL_REGISTRY["list_reminders"] = {
    "schema": {
        "name": "list_reminders",
        "description": "מציגה את כל התזכורות הפעילות של המשתמש",
        "input_schema": {
            "type": "object",
            "properties": {
                "chat_id": {"type": "string", "description": "chat_id will be filled by the framework; leave empty"},
            },
            "required": ["chat_id"],
        },
    },
    "fn": list_reminders,
}

TOOL_REGISTRY["cancel_reminder"] = {
    "schema": {
        "name": "cancel_reminder",
        "description": "מבטלת תזכורת לפי מזהה",
        "input_schema": {
            "type": "object",
            "properties": {
                "reminder_id": {"type": "string", "description": "מזהה התזכורת שרוצים לבטל"},
            },
            "required": ["reminder_id"],
        },
    },
    "fn": cancel_reminder,
}
