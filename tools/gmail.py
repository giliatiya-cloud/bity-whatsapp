from __future__ import annotations

import base64
from email.mime.text import MIMEText

import httpx
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

import config
from tools import TOOL_REGISTRY

_GMAIL_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"


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
        f"{_GMAIL_BASE}{path}",
        headers={"Authorization": f"Bearer {token}"},
        params=params or {},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def _post(path: str, body: dict) -> dict:
    token = _access_token()
    r = httpx.post(
        f"{_GMAIL_BASE}{path}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=body,
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def _decode_body(payload: dict) -> str:
    if payload.get("mimeType") == "text/plain":
        data = payload.get("body", {}).get("data", "")
        if data:
            return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
    for part in payload.get("parts", []):
        text = _decode_body(part)
        if text:
            return text
    return ""


def search_emails(query: str, max_results: int = 10) -> str:
    data = _get("/messages", {"q": query, "maxResults": max_results})
    messages = data.get("messages", [])
    if not messages:
        return "לא נמצאו מיילים תואמים לחיפוש."

    lines = []
    for m in messages:
        msg = _get(f"/messages/{m['id']}", {
            "format": "metadata",
            "metadataHeaders": "Subject,From,Date",
        })
        headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
        snippet = msg.get("snippet", "")[:120]
        lines.append(
            f"מזהה: {m['id']}\n"
            f"מאת: {headers.get('From', '?')}\n"
            f"נושא: {headers.get('Subject', '(ללא נושא)')}\n"
            f"תאריך: {headers.get('Date', '?')}\n"
            f"תקציר: {snippet}\n"
        )
    return "\n---\n".join(lines)


def get_email(message_id: str) -> str:
    msg = _get(f"/messages/{message_id}", {"format": "full"})
    headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
    body = _decode_body(msg.get("payload", {}))
    return (
        f"מאת: {headers.get('From', '?')}\n"
        f"נושא: {headers.get('Subject', '(ללא נושא)')}\n"
        f"תאריך: {headers.get('Date', '?')}\n\n"
        f"{body[:3000]}"
    )


def create_draft(to: str, subject: str, body: str) -> str:
    mime = MIMEText(body, "plain", "utf-8")
    mime["to"] = to
    mime["subject"] = subject
    raw = base64.urlsafe_b64encode(mime.as_bytes()).decode()
    draft = _post("/drafts", {"message": {"raw": raw}})
    draft_id = draft.get("id", "?")
    return f"טיוטה נוצרה (מזהה: {draft_id}). תוכל לעיין בה ב-Gmail ולשלוח ידנית."


TOOL_REGISTRY["search_emails"] = {
    "schema": {
        "name": "search_emails",
        "description": "מחפשת מיילים ב-Gmail לפי מחרוזת חיפוש (שולח, נושא, תוכן). מחזירה רשימת תוצאות.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "מחרוזת חיפוש, למשל 'from:boss@example.com' או 'חשבונית' או 'is:unread'",
                },
                "max_results": {
                    "type": "integer",
                    "description": "מספר מקסימלי של תוצאות (ברירת מחדל: 10)",
                },
            },
            "required": ["query"],
        },
    },
    "fn": search_emails,
}

TOOL_REGISTRY["get_email"] = {
    "schema": {
        "name": "get_email",
        "description": "קוראת את התוכן המלא של מייל לפי מזהה שהתקבל מ-search_emails",
        "input_schema": {
            "type": "object",
            "properties": {
                "message_id": {"type": "string", "description": "מזהה המייל"},
            },
            "required": ["message_id"],
        },
    },
    "fn": get_email,
}

TOOL_REGISTRY["create_email_draft"] = {
    "schema": {
        "name": "create_email_draft",
        "description": "יוצרת טיוטת מייל ב-Gmail — לא שולחת אוטומטית. המשתמש מאשר ושולח בעצמו.",
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {"type": "string", "description": "כתובת הנמען, למשל someone@example.com"},
                "subject": {"type": "string", "description": "נושא המייל"},
                "body": {"type": "string", "description": "תוכן המייל"},
            },
            "required": ["to", "subject", "body"],
        },
    },
    "fn": create_draft,
}
