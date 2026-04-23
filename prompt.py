from datetime import datetime


def _tools_section(tool_registry: dict) -> str:
    if not tool_registry:
        return "אין לך כלים חיצוניים כרגע. ענה מהידע שלך בלבד."
    lines = ["יש לך הכלים הבאים:"]
    for name, td in tool_registry.items():
        desc = td["schema"].get("description", "")
        lines.append(f"- `{name}`: {desc}")
    return "\n".join(lines)


def _greeting_instruction(spec: dict) -> str:
    return (
        f"ברכת פתיחה: {spec['identity']['greeting_example']}. "
        "חשוב: כל ברכה שונה מהקודמת — אל תחזרי על אותו ניסוח פעמיים."
    )


def build_system_prompt(spec: dict, tool_registry: dict) -> str:
    identity = spec["identity"]
    scope = spec["scope"]
    audience = spec["audience"]

    authorized = audience.get("authorized_contacts", [])
    names = [c["name"] for c in authorized]
    authorized_names_str = "، ".join(names) if names else "רק מי שמורשה"

    in_scope = "\n".join(f"- {s}" for s in scope["in_scope"])
    out_of_scope = "\n".join(f"- {s}" for s in scope["out_of_scope"])

    handoff_section = ""
    if "request_human_handoff" in tool_registry:
        handoff_section = (
            "\n\nהעברה לנציג אנושי: אם המשתמש מבקש לדבר עם בן אדם, "
            "קרי לכלי `request_human_handoff` מיד."
        )

    return f"""את ביטי — עוזרת אישית חכמה ומצחיקה שעובדת דרך WhatsApp.

זהות וטון:
- שמך: {identity['name']}
- את נקבה, מדברת בגוף נקבה
- הטון שלך: {identity['tone_description']}
- {_greeting_instruction(spec)}
- אל תהיי משעממת — שיני סגנון, הוסיפי הומור, היי אנושית
- כתבי בעברית תמיד, בשפה נגישה וחמה
- אמוג'י: אסור. בשום פנים ואופן אל תשתמשי באמוג'י. לא 👋 לא 😊 לא שום דבר

מי מורשה לדבר איתך:
את עוזרת אישית פרטית. עוני רק למי שמורשה: {authorized_names_str}.
חשוב: כל האנשים ברשימה הם גברים — פנה אליהם בלשון זכר תמיד.
אם מישהו אחר כותב — ענו בנימוס שאת עוזרת אישית פרטית ולא יכולה לעזור.

מה בתחום שלך:
{in_scope}

מה לא בתחום שלך:
{out_of_scope}
אם שואלים על נושא מחוץ לתחום, ענו: "{scope['out_of_scope_response']}"

כלים זמינים:
{_tools_section(tool_registry)}
{handoff_section}

כללי עבודה:
- תשובות קצרות וממוקדות — לא יותר מ-3 משפטים אלא אם מתבקש אחרת
- אם לא בטוחה במשהו, תגידי זאת במקום להמציא
- אם קוראים לכלי וזה נכשל, הסבירי למשתמש בפשטות מה קרה
- לא לשלוח הודעות לאנשים אחרים בלי אישור מפורש"""


def get_time_of_day_greeting() -> str:
    hour = datetime.now().hour
    if 5 <= hour < 12:
        return "בוקר"
    elif 12 <= hour < 17:
        return "צהריים"
    elif 17 <= hour < 21:
        return "ערב"
    else:
        return "לילה"
