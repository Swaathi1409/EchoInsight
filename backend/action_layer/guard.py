"""
backend/action_layer/guard.py
Master switch guard for the Action Intelligence Layer.

The DB toggle (act_settings.enabled) is the single gate.
In production, add ACTION_LAYER_ENABLED=true to your env to seed the
act_settings row; in development the seed-demo endpoint handles this.
"""
from __future__ import annotations

from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.action_layer.config import DISABLED_RESPONSE
from backend.action_layer.models import ActSettings
from backend.db import DbSession


async def _get_action_settings(session: AsyncSession) -> ActSettings | None:
    return (await session.execute(select(ActSettings).limit(1))).scalars().first()


async def is_action_layer_enabled(session: DbSession) -> bool:
    """Return True when the DB toggle is on (act_settings.enabled=True).
    
    The seed-demo endpoint and the /settings POST both set this flag.
    No env-var gate — the DB is the single source of truth for the toggle.
    """
    settings = await _get_action_settings(session)
    if settings is None:
        return False
    return bool(settings.enabled)


def disabled_response() -> JSONResponse:
    return JSONResponse(content=DISABLED_RESPONSE, status_code=200)
