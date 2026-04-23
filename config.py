import json
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

def _require(name: str) -> str:
    val = os.getenv(name)
    if not val:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return val

GREEN_API_URL = _require("GREEN_API_URL")
GREEN_API_INSTANCE = _require("GREEN_API_INSTANCE")
GREEN_API_TOKEN = _require("GREEN_API_TOKEN")

LLM_PROVIDER = _require("LLM_PROVIDER")
LLM_MODEL = _require("LLM_MODEL")
ANTHROPIC_API_KEY = _require("ANTHROPIC_API_KEY") if LLM_PROVIDER == "anthropic" else None

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REFRESH_TOKEN = os.getenv("GOOGLE_REFRESH_TOKEN")

DATABASE_URL = os.getenv("DATABASE_URL") or None
DATABASE_PATH = os.getenv("DATABASE_PATH", "data/conversations.db")
MAX_HISTORY = int(os.getenv("MAX_HISTORY", "20"))

_spec_path = Path(__file__).parent / "spec.json"
with open(_spec_path, encoding="utf-8") as f:
    SPEC = json.load(f)

BOT_NAME = SPEC["identity"]["name"]
ARCHETYPE = SPEC["archetype"]
AUTHORIZED_CONTACTS = {
    c["phone_e164"] for c in SPEC["audience"].get("authorized_contacts", [])
}
ANSWER_GROUPS = SPEC["audience"].get("answer_groups", False)
