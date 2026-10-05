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
    - ASSISTANT_ENABLED=true  → always enabled (hard-enable)
    - ASSISTANT_ENABLED=false → always disabled (hard-disable)
    - Not set                 → check asst_settings.enabled in DB
    """
    env_val = os.getenv("ASSISTANT_ENABLED", "").lower().replace('"', '').replace("'", "").strip()
    if env_val in ("true", "1", "yes"):
        return True   # hard-enabled by env
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
