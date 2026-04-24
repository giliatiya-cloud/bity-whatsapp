from __future__ import annotations

import logging

from fastapi import FastAPI, Request

import config
import database
from tools.whatsapp import send_reply

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="ביטי WhatsApp Agent")

database.init_db()

_OWN_JID = f"{config.GREEN_API_INSTANCE}@c.us"


@app.get("/health")
def health():
    return {"status": "ok", "bot": config.BOT_NAME, "version": 1}


@app.get("/debug/calendar")
def debug_calendar():
    """Temporary: test Google Calendar API from Render environment."""
    try:
        from tools.google_calendar import _access_token, list_events
        token = _access_token()
        events = list_events("2026-04-24", "2026-04-30")
        return {"ok": True, "token_prefix": token[:10] + "...", "events": events}
    except Exception as e:
        import traceback
        return {"ok": False, "error": str(e), "trace": traceback.format_exc()}


@app.post("/webhook/green-api")
async def webhook(request: Request):
    try:
        body = await request.json()
    except Exception:
        return {"ok": False, "reason": "invalid json"}

    if body.get("typeWebhook") != "incomingMessageReceived":
        return {"ok": True, "reason": "ignored"}

    message_data = body.get("messageData", {})
    if message_data.get("typeMessage") != "textMessage":
        return {"ok": True, "reason": "non-text ignored"}

    sender_data = body.get("senderData", {})
    chat_id: str = sender_data.get("chatId", "")
    sender: str = sender_data.get("sender", chat_id)
    id_message: str = body.get("idMessage", "")

    if sender == _OWN_JID or chat_id == _OWN_JID:
        return {"ok": True, "reason": "own message ignored"}

    if chat_id.endswith("@g.us") and not config.ANSWER_GROUPS:
        return {"ok": True, "reason": "group ignored"}

    if database.is_processed(id_message):
        return {"ok": True, "reason": "duplicate"}
    database.mark_processed(id_message)

    sender_phone = sender.replace("@c.us", "").replace("@s.whatsapp.net", "")
    if config.ARCHETYPE == "personal_assistant" and sender_phone not in config.AUTHORIZED_CONTACTS:
        logger.info("Unauthorized sender: %s", sender_phone)
        send_reply(chat_id, "שלום! אני ביטי, עוזרת אישית פרטית. לצערי אני לא יכולה לעזור לך 😊")
        return {"ok": True, "reason": "unauthorized"}

    text: str = message_data.get("textMessageData", {}).get("textMessage", "")
    if not text.strip():
        return {"ok": True, "reason": "empty message"}

    logger.info("Message from %s: %s", sender_phone, text[:80])

    try:
        from agent import handle_message
        reply = handle_message(chat_id, sender_phone, text)
        try:
            send_reply(chat_id, reply)
            logger.info("Replied: %s", reply[:80])
        except Exception as send_err:
            logger.error("Failed to send reply: %s", send_err)
    except Exception as e:
        logger.exception("Error handling message: %s", e)
        try:
            send_reply(chat_id, "אופס, נתקלתי בבעיה טכנית קטנה. נסה שוב בעוד רגע")
        except Exception:
            pass

    return {"ok": True}
