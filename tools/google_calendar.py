from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

import config
from tools import TOOL_REGISTRY


def _service():
    creds = Credentials(
        token=None,
        refresh_token=config.GOOGLE_REFRESH_TOKEN,
        client_id=config.GOOGLE_CLIENT_ID,
        client_secret=config.GOOGLE_CLIENT_SECRET,
        token_uri="https://oauth2.googleapis.com/token",
    )
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def _fmt_event(e: dict) -> str:
    summary = e.get("summary", "(ללא שם)")
    start = e.get("start", {})
    dt = start.get("dateTime") or start.get("date", "")
    location = e.get("location", "")
    loc_part = f" | {location}" if location else ""
    if "T" in dt:
        try:
            parsed = datetime.fromisoformat(dt)
            dt = parsed.strftime("%d/%m %H:%M")
        except Exception:
            pass
    return f"{dt} — {summary}{loc_part}"


_IL_TZ = timezone(timedelta(hours=3))


def _to_il_iso(date_str: str, end_of_day: bool = False) -> str:
    """Convert YYYY-MM-DD or full ISO string to Israel-timezone ISO timestamp."""
    if "T" in date_str and ("+" in date_str or "Z" in date_str):
        return date_str  # already has timezone, use as-is
    if "T" in date_str:
        # has time but no tz — treat as Israel time
        dt = datetime.fromisoformat(date_str).replace(tzinfo=_IL_TZ)
    else:
        # date only — expand to start or end of day
        d = datetime.fromisoformat(date_str).date()
        if end_of_day:
            dt = datetime(d.year, d.month, d.day, 23, 59, 59, tzinfo=_IL_TZ)
        else:
            dt = datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=_IL_TZ)
    return dt.isoformat()


def list_events(date_from: str, date_to: str) -> str:
    """List events between two dates. Accepts YYYY-MM-DD or full ISO 8601."""
    svc = _service()
    result = (
        svc.events()
        .list(
            calendarId="primary",
            timeMin=_to_il_iso(date_from, end_of_day=False),
            timeMax=_to_il_iso(date_to, end_of_day=True),
            singleEvents=True,
            orderBy="startTime",
            maxResults=20,
        )
        .execute()
    )
    events = result.get("items", [])
    if not events:
        return "אין אירועים בטווח הזמן הזה."
    return "\n".join(_fmt_event(e) for e in events)


def create_event(summary: str, start_iso: str, end_iso: str, location: str = "", description: str = "") -> str:
    svc = _service()
    body: dict[str, Any] = {
        "summary": summary,
        "start": {"dateTime": start_iso, "timeZone": "Asia/Jerusalem"},
        "end": {"dateTime": end_iso, "timeZone": "Asia/Jerusalem"},
    }
    if location:
        body["location"] = location
    if description:
        body["description"] = description
    event = svc.events().insert(calendarId="primary", body=body).execute()
    link = event.get("htmlLink", "")
    return f"אירוע נוצר: {summary} ב-{start_iso[:16].replace('T', ' ')}" + (f"\n{link}" if link else "")


def delete_event(event_id: str) -> str:
    svc = _service()
    svc.events().delete(calendarId="primary", eventId=event_id).execute()
    return f"האירוע {event_id} נמחק."


def get_event_id_by_summary(summary_contains: str, date_from: str, date_to: str) -> str:
    """Find event IDs matching a title substring — use before deleting."""
    svc = _service()
    result = (
        svc.events()
        .list(
            calendarId="primary",
            timeMin=_to_il_iso(date_from, end_of_day=False),
            timeMax=_to_il_iso(date_to, end_of_day=True),
            q=summary_contains,
            singleEvents=True,
            orderBy="startTime",
            maxResults=5,
        )
        .execute()
    )
    events = result.get("items", [])
    if not events:
        return "לא נמצאו אירועים תואמים."
    lines = [f"{e.get('id')} — {_fmt_event(e)}" for e in events]
    return "\n".join(lines)


TOOL_REGISTRY["list_calendar_events"] = {
    "schema": {
        "name": "list_calendar_events",
        "description": "מציגה אירועים ביומן Google של המשתמש בין שני תאריכים. קבלי תאריכים בפורמט YYYY-MM-DD.",
        "input_schema": {
            "type": "object",
            "properties": {
                "date_from": {
                    "type": "string",
                    "description": "תאריך התחלה בפורמט YYYY-MM-DD, למשל 2026-04-25",
                },
                "date_to": {
                    "type": "string",
                    "description": "תאריך סיום בפורמט YYYY-MM-DD, למשל 2026-04-25 (אותו יום להצגת יום אחד)",
                },
            },
            "required": ["date_from", "date_to"],
        },
    },
    "fn": list_events,
}

TOOL_REGISTRY["create_calendar_event"] = {
    "schema": {
        "name": "create_calendar_event",
        "description": "יוצרת אירוע חדש ביומן Google של המשתמש",
        "input_schema": {
            "type": "object",
            "properties": {
                "summary": {"type": "string", "description": "שם האירוע"},
                "start_iso": {
                    "type": "string",
                    "description": "זמן התחלה בפורמט ISO 8601 עם timezone, למשל 2026-04-24T10:00:00+03:00",
                },
                "end_iso": {
                    "type": "string",
                    "description": "זמן סיום בפורמט ISO 8601 עם timezone, למשל 2026-04-24T11:00:00+03:00",
                },
                "location": {"type": "string", "description": "מיקום האירוע (אופציונלי)"},
                "description": {"type": "string", "description": "תיאור האירוע (אופציונלי)"},
            },
            "required": ["summary", "start_iso", "end_iso"],
        },
    },
    "fn": create_event,
}

TOOL_REGISTRY["delete_calendar_event"] = {
    "schema": {
        "name": "delete_calendar_event",
        "description": "מוחקת אירוע מהיומן לפי event_id",
        "input_schema": {
            "type": "object",
            "properties": {
                "event_id": {"type": "string", "description": "מזהה האירוע למחיקה"},
            },
            "required": ["event_id"],
        },
    },
    "fn": delete_event,
}

TOOL_REGISTRY["find_calendar_event_id"] = {
    "schema": {
        "name": "find_calendar_event_id",
        "description": "מוצאת מזהי אירועים ביומן לפי חלק מהשם — השתמשי בזה לפני מחיקה",
        "input_schema": {
            "type": "object",
            "properties": {
                "summary_contains": {"type": "string", "description": "מילת חיפוש בשם האירוע"},
                "date_from": {"type": "string", "description": "תחילת טווח חיפוש YYYY-MM-DD"},
                "date_to": {"type": "string", "description": "סוף טווח חיפוש YYYY-MM-DD"},
            },
            "required": ["summary_contains", "date_from", "date_to"],
        },
    },
    "fn": get_event_id_by_summary,
}
