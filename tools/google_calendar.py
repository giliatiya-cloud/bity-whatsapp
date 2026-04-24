from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any

import httpx
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

import config
from tools import TOOL_REGISTRY

_IL_TZ = timezone(timedelta(hours=3))
_CALENDAR_BASE = "https://www.googleapis.com/calendar/v3"


def _access_token() -> str:
    creds = Credentials(
        token=None,
        refresh_token=config.GOOGLE_REFRESH_TOKEN,
        client_id=config.GOOGLE_CLIENT_ID,
        client_secret=config.GOOGLE_CLIENT_SECRET,
        token_uri="https://oauth2.googleapis.com/token",
    )
    creds.refresh(Request())
    return creds.token


def _get(path: str, params: dict | None = None) -> dict:
    token = _access_token()
    r = httpx.get(
        f"{_CALENDAR_BASE}{path}",
        headers={"Authorization": f"Bearer {token}"},
        params=params or {},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def _post(path: str, body: dict) -> dict:
    token = _access_token()
    r = httpx.post(
        f"{_CALENDAR_BASE}{path}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=body,
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def _delete(path: str) -> None:
    token = _access_token()
    r = httpx.delete(
        f"{_CALENDAR_BASE}{path}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    r.raise_for_status()


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


def _to_il_iso(date_str: str, end_of_day: bool = False) -> str:
    if "T" in date_str and ("+" in date_str or "Z" in date_str):
        return date_str
    if "T" in date_str:
        dt = datetime.fromisoformat(date_str).replace(tzinfo=_IL_TZ)
    else:
        d = datetime.fromisoformat(date_str).date()
        if end_of_day:
            dt = datetime(d.year, d.month, d.day, 23, 59, 59, tzinfo=_IL_TZ)
        else:
            dt = datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=_IL_TZ)
    return dt.isoformat()


def list_events(date_from: str, date_to: str) -> str:
    data = _get("/calendars/primary/events", {
        "timeMin": _to_il_iso(date_from, end_of_day=False),
        "timeMax": _to_il_iso(date_to, end_of_day=True),
        "singleEvents": "true",
        "orderBy": "startTime",
        "maxResults": 20,
    })
    events = data.get("items", [])
    if not events:
        return "אין אירועים בטווח הזמן הזה."
    return "\n".join(_fmt_event(e) for e in events)


def create_event(summary: str, start_iso: str, end_iso: str, location: str = "", description: str = "") -> str:
    # Normalize to Israel timezone if no tz given
    start_iso = _to_il_iso(start_iso)
    end_iso = _to_il_iso(end_iso)
    body: dict[str, Any] = {
        "summary": summary,
        "start": {"dateTime": start_iso, "timeZone": "Asia/Jerusalem"},
        "end": {"dateTime": end_iso, "timeZone": "Asia/Jerusalem"},
    }
    if location:
        body["location"] = location
    if description:
        body["description"] = description
    event = _post("/calendars/primary/events", body)
    link = event.get("htmlLink", "")
    return f"אירוע נוצר: {summary} ב-{start_iso[:16].replace('T', ' ')}" + (f"\n{link}" if link else "")


def delete_event(event_id: str) -> str:
    _delete(f"/calendars/primary/events/{event_id}")
    return f"האירוע {event_id} נמחק."


def get_event_id_by_summary(summary_contains: str, date_from: str, date_to: str) -> str:
    data = _get("/calendars/primary/events", {
        "timeMin": _to_il_iso(date_from, end_of_day=False),
        "timeMax": _to_il_iso(date_to, end_of_day=True),
        "q": summary_contains,
        "singleEvents": "true",
        "orderBy": "startTime",
        "maxResults": 5,
    })
    events = data.get("items", [])
    if not events:
        return "לא נמצאו אירועים תואמים."
    return "\n".join(f"{e.get('id')} — {_fmt_event(e)}" for e in events)


TOOL_REGISTRY["list_calendar_events"] = {
    "schema": {
        "name": "list_calendar_events",
        "description": "מציגה אירועים ביומן Google של המשתמש בין שני תאריכים. קבלי תאריכים בפורמט YYYY-MM-DD.",
        "input_schema": {
            "type": "object",
            "properties": {
                "date_from": {"type": "string", "description": "תאריך התחלה YYYY-MM-DD, למשל 2026-04-25"},
                "date_to": {"type": "string", "description": "תאריך סיום YYYY-MM-DD, למשל 2026-04-25"},
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
                "start_iso": {"type": "string", "description": "זמן התחלה YYYY-MM-DDTHH:MM:SS למשל 2026-04-25T18:00:00"},
                "end_iso": {"type": "string", "description": "זמן סיום YYYY-MM-DDTHH:MM:SS למשל 2026-04-25T19:00:00"},
                "location": {"type": "string", "description": "מיקום (אופציונלי)"},
                "description": {"type": "string", "description": "תיאור (אופציונלי)"},
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
                "event_id": {"type": "string", "description": "מזהה האירוע"},
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
                "date_from": {"type": "string", "description": "תחילת טווח YYYY-MM-DD"},
                "date_to": {"type": "string", "description": "סוף טווח YYYY-MM-DD"},
            },
            "required": ["summary_contains", "date_from", "date_to"],
        },
    },
    "fn": get_event_id_by_summary,
}
