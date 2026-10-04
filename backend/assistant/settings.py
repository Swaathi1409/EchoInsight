"""
backend/assistant/settings.py
Master switch and runtime settings for the assistant.
ASSISTANT_ENABLED=false by default; admin can toggle at runtime via asst_settings table.
"""
from __future__ import annotations

import os
from functools import lru_cache


def assistant_env_enabled() -> bool:
    """Read ASSISTANT_ENABLED from environment on every call (no cache)."""
    return os.getenv("ASSISTANT_ENABLED", "false").lower() in ("1", "true", "yes")


async def is_assistant_enabled(session) -> bool:
    """
    Enabled when:
    - ASSISTANT_ENABLED env var is explicitly "false" or "0" → always disabled (hard block).
    - Otherwise: check asst_settings.enabled in DB.
    This allows toggling via admin DB in dev without restarting the server.
    In production, set ASSISTANT_ENABLED=false to hard-disable regardless of DB.
    """
    env_val = os.getenv("ASSISTANT_ENABLED", "").lower()
    if env_val in ("false", "0", "no"):
        return False  # hard-disabled by env
    from sqlalchemy import select
    from backend.assistant.models import AsstSettings
    row = (await session.execute(select(AsstSettings).limit(1))).scalars().first()
    if row is None:
        return False
    return bool(row.enabled)


def disabled_response() -> dict:
    return {"enabled": False, "message": "Assistant feature is disabled."}
