from __future__ import annotations

TOOL_REGISTRY: dict[str, dict] = {}

# Reminders tool
try:
    from tools import reminders as _reminders_module  # noqa: F401
except ImportError:
    pass

# Google Calendar
try:
    from tools import google_calendar as _gcal_module  # noqa: F401
except ImportError:
    pass
