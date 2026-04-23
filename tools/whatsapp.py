import httpx

import config


def send_reply(chat_id: str, text: str) -> None:
    url = f"{config.GREEN_API_URL}/waInstance{config.GREEN_API_INSTANCE}/sendMessage/{config.GREEN_API_TOKEN}"
    payload = {"chatId": chat_id, "message": text}
    with httpx.Client(timeout=15) as client:
        resp = client.post(url, json=payload)
        resp.raise_for_status()


def send_to_phone(phone_e164: str, text: str) -> None:
    chat_id = f"{phone_e164}@c.us"
    send_reply(chat_id, text)
