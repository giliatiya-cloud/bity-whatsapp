from __future__ import annotations

import anthropic

import config
import database
from prompt import build_system_prompt
from tools import TOOL_REGISTRY

_client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

FRAMEWORK_INJECTED_CHAT_ID = {
    "schedule_reminder",
    "list_reminders",
    "cancel_reminder",
    "create_reminder",
}

MAX_TOOL_ITERATIONS = 5

# Keywords that signal an action request — force tool use when detected
_ACTION_KEYWORDS = [
    "קבע", "תקבע", "תקבעי", "לקבוע", "הוסף", "תוסיפי", "צור", "תצורי",
    "מחק", "תמחקי", "בטל", "תבטלי",
    "שלח", "תשלחי", "לשלוח", "כתוב", "תכתבי", "הכן", "תכיני", "טיוטה",
    "תזכיר", "תזמן",
]


def _requires_tool(message: str) -> bool:
    msg_lower = message.lower()
    return any(kw in msg_lower for kw in _ACTION_KEYWORDS)


def _run_tool(tool_use, chat_id: str) -> tuple[str, bool]:
    """Returns (result_text, is_error)."""
    if tool_use.name not in TOOL_REGISTRY:
        return f"כלי לא מוכר: {tool_use.name}", True

    tool_def = TOOL_REGISTRY[tool_use.name]
    tool_input = dict(tool_use.input or {})

    if tool_use.name in FRAMEWORK_INJECTED_CHAT_ID:
        tool_input["chat_id"] = chat_id

    try:
        result = tool_def["fn"](**tool_input)
        return str(result), False
    except Exception as e:
        import logging
        logging.error("Tool %s failed: %s", tool_use.name, e, exc_info=True)
        return f"שגיאה: {e}", True


def handle_message(chat_id: str, sender_phone: str, message_text: str) -> str:
    history = database.tail(chat_id)
    system_prompt = build_system_prompt(config.SPEC, TOOL_REGISTRY)

    messages = history + [{"role": "user", "content": message_text}]
    tools = [td["schema"] for td in TOOL_REGISTRY.values()]

    database.append(chat_id, "user", message_text)

    for iteration in range(MAX_TOOL_ITERATIONS):
        kwargs: dict = {
            "model": config.LLM_MODEL,
            "max_tokens": 1024,
            "system": system_prompt,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools
            if _requires_tool(message_text):
                kwargs["tool_choice"] = {"type": "any"}

        response = _client.messages.create(**kwargs)

        import logging as _log
        _log.info("LLM stop_reason=%s iteration=%d", response.stop_reason, iteration)
        if response.stop_reason == "end_turn":
            reply = _extract_text(response)
            database.append(chat_id, "assistant", reply)
            return reply

        if response.stop_reason == "tool_use":
            tool_uses = [b for b in response.content if b.type == "tool_use"]
            tool_results = []

            for tool_use in tool_uses:
                import logging as _log
                _log.info("TOOL CALL: %s(%s)", tool_use.name, tool_use.input)
                result, is_error = _run_tool(tool_use, chat_id)
                _log.info("TOOL RESULT (error=%s): %s", is_error, str(result)[:200])
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": str(result),
                    "is_error": is_error,
                })

            messages = messages + [
                {"role": "assistant", "content": response.content},
                {"role": "user", "content": tool_results},
            ]
            continue

        break

    reply = "סליחה, נתקלתי בבעיה. נסה שוב בעוד רגע."
    database.append(chat_id, "assistant", reply)
    return reply


def _extract_text(response) -> str:
    for block in response.content:
        if hasattr(block, "text"):
            return block.text
    return "קיבלתי את ההודעה."
