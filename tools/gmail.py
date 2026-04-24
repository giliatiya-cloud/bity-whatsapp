from __future__ import annotations

import base64
import email as email_lib
from email.mime.text import MIMEText

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
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def _decode_body(payload: dict) -> str:
    """Extract plain text body from Gmail message payload."""
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
    """Search Gmail inbox. Returns subject, from, date and snippet."""
    svc = _service()
    result = svc.users().messages().list(
        userId="me", q=query, maxResults=max_results
    ).execute()
    messages = result.get("messages", [])
    if not messages:
        return "לא נמצאו מיילים תואמים לחיפוש."

    lines = []
    for m in messages:
        msg = svc.users().messages().get(
            userId="me", id=m["id"], format="metadata",
            metadataHeaders=["Subject", "From", "Date"]
        ).execute()
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
    """Get full body of a Gmail message by ID."""
    svc = _service()
    msg = svc.users().messages().get(
        userId="me", id=message_id, format="full"
    ).execute()
    headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
    body = _decode_body(msg.get("payload", {}))
    return (
        f"מאת: {headers.get('From', '?')}\n"
        f"נושא: {headers.get('Subject', '(ללא נושא)')}\n"
        f"תאריך: {headers.get('Date', '?')}\n\n"
        f"{body[:3000]}"
    )


def create_draft(to: str, subject: str, body: str) -> str:
    """Create a Gmail draft (does NOT send — user must review and send manually)."""
    svc = _service()
    mime = MIMEText(body, "plain", "utf-8")
    mime["to"] = to
    mime["subject"] = subject
    raw = base64.urlsafe_b64encode(mime.as_bytes()).decode()
    draft = svc.users().drafts().create(
        userId="me", body={"message": {"raw": raw}}
    ).execute()
    draft_id = draft.get("id", "?")
    return f"טיוטה נוצרה (מזהה: {draft_id}). תוכל לעיין בה ב-Gmail ולשלוח ידנית."


TOOL_REGISTRY["search_emails"] = {
    "schema": {
        "name": "search_emails",
        "description": "מחפשת מיילים ב-Gmail לפי מחרוזת חיפוש (שם שולח, נושא, מילה בתוכן). מחזירה רשימת תוצאות.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "מחרוזת חיפוש, כמו 'from:boss@example.com' או 'חשבונית' או 'is:unread'",
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
                "message_id": {
                    "type": "string",
                    "description": "מזהה המייל מחיפוש קודם",
                },
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
                "to": {
                    "type": "string",
                    "description": "כתובת הנמען, למשל someone@example.com",
                },
                "subject": {
                    "type": "string",
                    "description": "נושא המייל",
                },
                "body": {
                    "type": "string",
                    "description": "תוכן המייל",
                },
            },
            "required": ["to", "subject", "body"],
        },
    },
    "fn": create_draft,
}
