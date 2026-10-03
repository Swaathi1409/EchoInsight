"""
backend/action_layer/guard.py
Master switch guard for the Action Intelligence Layer.

Every action layer endpoint must call require_enabled() first.
When disabled, returns a 200 response with enabled=false (not a 4xx).
"""
from __future__ import annotations

from fastapi import Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.action_layer.config import ACTION_LAYER_ENABLED_ENV, DISABLED_RESPONSE
from backend.action_layer.models import ActSettings
from backend.db import get_db_session
from sqlalchemy import select


async def _get_action_settings(session: AsyncSession) -> ActSettings | None:
    return (await session.execute(select(ActSettings).limit(1))).scalars().first()


async def is_action_layer_enabled(
    session: AsyncSession = Depends(get_db_session),
) -> bool:
    """Return True only when both the env flag AND the DB toggle are on."""
    if not ACTION_LAYER_ENABLED_ENV:
        return False
    settings = await _get_action_settings(session)
    if settings is None:
        return False
    return settings.enabled


def disabled_response() -> JSONResponse:
    return JSONResponse(content=DISABLED_RESPONSE, status_code=200)
