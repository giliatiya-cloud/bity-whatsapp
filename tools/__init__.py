from __future__ import annotations

TOOL_REGISTRY: dict[str, dict] = {}

# External tools (gmail, google_calendar, whatsapp_groups, human_handoff)
# are added here by wa-connect after deploy.

# Reminders tool is registered below if available.
try:
    from tools import reminders as _reminders_module  # noqa: F401
except ImportError:
    pass
