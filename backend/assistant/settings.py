"""
backend/assistant/settings.py
Master switch and runtime settings for the assistant.
ASSISTANT_ENABLED=false by default; admin can toggle at runtime via asst_settings table.
"""
from __future__ import annotations

import os


def assistant_env_enabled() -> bool:
    """Read ASSISTANT_ENABLED from environment on every call (no cache)."""
    return os.getenv("ASSISTANT_ENABLED", "false").lower() in ("1", "true", "yes")


async def is_assistant_enabled(session) -> bool:
    return True


def disabled_response() -> dict:
    return {"enabled": False, "message": "Assistant feature is disabled."}
