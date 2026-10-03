"""
backend/action_layer/api/router.py
Main router that aggregates all action layer sub-routers.

When the master switch is off every endpoint returns:
  {"enabled": false, "detail": "Action layer is disabled."}
with HTTP 200 so the frontend can detect the state cleanly.

Sub-routers are registered here; they will be built in Phase 2+.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from backend.action_layer.guard import is_action_layer_enabled, disabled_response
from backend.action_layer.config import DISABLED_RESPONSE

router = APIRouter(prefix="/action", tags=["action-layer"])


# ── Health / status endpoint (always returns, reveals enabled state) ──────────

@router.get("/status")
async def action_layer_status(
    enabled: bool = Depends(is_action_layer_enabled),
) -> dict:
    """Returns whether the action layer is enabled. Safe to call always."""
    return {"enabled": enabled}


# ── Settings (admin only) ─────────────────────────────────────────────────────

@router.get("/settings")
async def get_settings(
    enabled: bool = Depends(is_action_layer_enabled),
) -> JSONResponse:
    if not enabled:
        return disabled_response()
    # Full implementation in Phase 2
    return JSONResponse({"detail": "Phase 2 implementation pending"}, status_code=501)


@router.post("/settings")
async def update_settings(
    enabled: bool = Depends(is_action_layer_enabled),
) -> JSONResponse:
    if not enabled:
        return disabled_response()
    return JSONResponse({"detail": "Phase 2 implementation pending"}, status_code=501)


# ── Derive job endpoints (admin only) ─────────────────────────────────────────

@router.get("/derive/status")
async def derive_status(
    enabled: bool = Depends(is_action_layer_enabled),
) -> JSONResponse:
    if not enabled:
        return disabled_response()
    return JSONResponse({"detail": "Phase 2 implementation pending"}, status_code=501)


@router.post("/derive/run")
async def derive_run(
    enabled: bool = Depends(is_action_layer_enabled),
) -> JSONResponse:
    if not enabled:
        return disabled_response()
    return JSONResponse({"detail": "Phase 2 implementation pending"}, status_code=501)


# ── Recovery Desk items ───────────────────────────────────────────────────────

@router.get("/items")
async def list_items(
    enabled: bool = Depends(is_action_layer_enabled),
) -> JSONResponse:
    if not enabled:
        return disabled_response()
    return JSONResponse({"detail": "Phase 2 implementation pending"}, status_code=501)


@router.get("/items/{item_id}")
async def get_item(
    item_id: int,
    enabled: bool = Depends(is_action_layer_enabled),
) -> JSONResponse:
    if not enabled:
        return disabled_response()
    return JSONResponse({"detail": "Phase 2 implementation pending"}, status_code=501)


# ── Recurring Issues ──────────────────────────────────────────────────────────

@router.get("/issues")
async def list_issues(
    enabled: bool = Depends(is_action_layer_enabled),
) -> JSONResponse:
    if not enabled:
        return disabled_response()
    return JSONResponse({"detail": "Phase 3 implementation pending"}, status_code=501)


# ── PDCA Initiatives ──────────────────────────────────────────────────────────

@router.get("/initiatives")
async def list_initiatives(
    enabled: bool = Depends(is_action_layer_enabled),
) -> JSONResponse:
    if not enabled:
        return disabled_response()
    return JSONResponse({"detail": "Phase 3 implementation pending"}, status_code=501)


# ── Agent Insights ────────────────────────────────────────────────────────────

@router.get("/agents/{agent_id}/profile")
async def agent_profile(
    agent_id: str,
    enabled: bool = Depends(is_action_layer_enabled),
) -> JSONResponse:
    if not enabled:
        return disabled_response()
    return JSONResponse({"detail": "Phase 4 implementation pending"}, status_code=501)
