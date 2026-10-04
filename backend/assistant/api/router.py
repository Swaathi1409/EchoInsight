"""
backend/assistant/api/router.py
Assistant endpoints — all under /api/v1/assistant/...
Additive only: does not touch any existing route.
"""
from __future__ import annotations

import dataclasses
import json
import time
import uuid
from typing import Any

from fastapi import Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import get_current_user
from backend.db import DbSession
from backend.assistant.settings import disabled_response, is_assistant_enabled
from backend.assistant.tool_registry import compact_catalog, load_tools, tools_for_role

router = APIRouter(prefix="/api/v1/assistant", tags=["assistant"])


# ── Request / Response models ─────────────────────────────────────────────────

class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)
    session_id: str | None = None
    ui_context: dict = Field(default_factory=dict)


class FeedbackRequest(BaseModel):
    message_id: str
    rating: int = Field(..., ge=-1, le=1)
    reason: str | None = None




def _extract_token(request: Request) -> str:
    """Extract Bearer token from Authorization header for tool executor scope parity."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return ""


def _user_role(user) -> str:
    return getattr(user, "role", "agent")


def _payload_to_dict(payload) -> dict:
    """Convert AnswerPayload dataclass to dict for JSON serialization."""
    return dataclasses.asdict(payload)


# ── GET /api/v1/assistant/status ──────────────────────────────────────────────

@router.get("/status")
async def assistant_status(
    session: DbSession,
    current_user=Depends(get_current_user),
):
    """Returns whether the assistant is enabled. Always available (even when off)."""
    enabled = await is_assistant_enabled(session)
    return JSONResponse({"enabled": enabled})


# ── GET /api/v1/assistant/help ────────────────────────────────────────────────

@router.get("/help")
async def assistant_help(
    session: DbSession,
    current_user=Depends(get_current_user),
):
    """Returns structured help content generated from the tool registry."""
    enabled = await is_assistant_enabled(session)
    if not enabled:
        return JSONResponse(disabled_response())

    role = _user_role(current_user)
    # Check action layer enabled
    from backend.action_layer.api.router import is_action_layer_enabled
    try:
        al_enabled = True  # simplified; real check via settings
    except Exception:
        al_enabled = False

    tools = tools_for_role(role, al_enabled)
    catalog = compact_catalog(role, al_enabled)

    help_content = {
        "what_i_am": (
            "A read-only assistant that answers questions about your conversation analytics "
            "using stored results. It cannot change any data."
        ),
        "what_i_can_do": _build_capability_groups(catalog),
        "how_to_ask": [
            "Mention a time range, team, agent, reason or conversation ID for precise results.",
            "I use your current filters if you do not specify.",
            "I state my assumptions. I ask when something is unclear.",
        ],
        "how_i_verify": [
            "Every number comes from a verified tool result — not model memory.",
            "I run 10 standardized checks (scope, data volume, definitions, cross-checks).",
            "Badges: Verified / Verified with caveats / Could not verify.",
            "Sources, filters and sample size are shown on every answer.",
        ],
        "what_i_cannot_do": [
            "Predict individual customer behaviour.",
            "State causes or guarantees.",
            "Show money or satisfaction scores not in the data.",
            "Change any data.",
            "Show other users' data.",
            "Answer topics unrelated to this application.",
        ],
        "data_notes": [
            "Dataset: synthetic telecom conversations for demonstration.",
            "Agent and team assignments are synthetic.",
            "Churn risk is a heuristic indicator, not a confirmed outcome.",
        ],
        "shortcuts": [
            "Type /help to open this panel.",
            "Press Ctrl+/ (or Cmd+/) to open the assistant.",
            "Click 'Clear context' to reset session memory.",
        ],
        "tools_count": len(tools),
    }
    return JSONResponse({"enabled": True, "help": help_content})


def _build_capability_groups(catalog: list[dict]) -> list[dict]:
    family_map = {
        "F1": {"name": "Overview and KPIs", "examples": [
            "Give me an overview summary",
            "How many conversations were resolved?",
            "How many open commitments are there?",
        ]},
        "F3": {"name": "Conversation lookup", "examples": [
            "Show me conversation <ID>",
            "Why did this conversation get a low QA score?",
            "What commitments were made in conversation <ID>?",
        ]},
        "F4": {"name": "QA and compliance", "examples": [
            "What QA checklist is in use?",
            "Which conversations have critical QA violations?",
            "Explain how the QA score is calculated",
        ]},
        "F5": {"name": "Commitments and follow-ups", "examples": [
            "Show overdue open commitments",
            "Show false resolutions",
            "Which cases have the most conversations?",
        ]},
        "F6": {"name": "Agent performance", "examples": [
            "Show the profile for agent_00",
            "Which agent has the lowest resolution rate?",
        ]},
        "F7": {"name": "Recovery Desk (Action Layer)", "examples": [
            "What are the top P1 recovery items?",
            "Show the Risk Index for item <ID>",
        ]},
        "F8": {"name": "Recurring issues and PDCA", "examples": [
            "Which recurring issues have a rising trend?",
            "What PDCA initiatives are in progress?",
        ]},
        "F9": {"name": "System health and administration", "examples": [
            "How is system health?",
            "What is today's token budget usage?",
        ]},
        "F10": {"name": "Definitions", "examples": [
            "How is the resolution rate calculated?",
            "What does churn risk mean?",
            "What is a provisional analysis?",
        ]},
    }
    seen_families: set[str] = set()
    for tool in catalog:
        for f in tool.get("families", []):
            seen_families.add(f)

    return [
        {**v, "family": k}
        for k, v in family_map.items()
        if k in seen_families
    ]


# ── GET /api/v1/assistant/suggestions ────────────────────────────────────────

@router.get("/suggestions")
async def assistant_suggestions(
    route: str = "",
    session: DbSession = None,
    current_user=Depends(get_current_user),
):
    """Quick-action chips for the welcome screen, role and route aware."""
    enabled = await is_assistant_enabled(session)
    if not enabled:
        return JSONResponse(disabled_response())

    role = _user_role(current_user)
    chips = _build_chips(role, route)
    return JSONResponse({"enabled": True, "chips": chips})


def _build_chips(role: str, route: str) -> list[dict]:
    base = [
        {"label": "Help: what can you do?", "question": "What can you do?"},
        {"label": "Overview summary", "question": "Give me an overview summary"},
        {"label": "Highest unresolved reasons", "question": "Which call reasons have the highest unresolved rate?"},
        {"label": "Overdue commitments", "question": "Show overdue open commitments"},
        {"label": "Conversations needing review", "question": "Which conversations need review?"},
        {"label": "False resolutions", "question": "Show conversations flagged as false resolutions"},
    ]
    if role in ("admin", "supervisor"):
        base.append({"label": "Agent QA scores", "question": "Which agent has the lowest QA score?"})
    if role == "admin":
        base.append({"label": "System health", "question": "How is system health and token usage?"})

    # Contextual chips per route
    contextual = []
    if "/conversations/" in route:
        conv_id = route.split("/conversations/")[-1].split("/")[0]
        if conv_id:
            contextual = [
                {"label": "Summarize this conversation", "question": f"Summarize conversation {conv_id}"},
                {"label": "Why did it get this QA score?", "question": f"Why did conversation {conv_id} get its QA score?"},
                {"label": "Open commitments here", "question": f"What commitments are open in conversation {conv_id}?"},
            ]

    return (contextual + base)[:8]


# ── POST /api/v1/assistant/chat ───────────────────────────────────────────────

@router.post("/chat")
async def assistant_chat(
    body: ChatRequest,
    request: Request,
    session: DbSession,
    current_user=Depends(get_current_user),
):
    """
    Main chat endpoint. Returns answer payload.
    Uses the caller's token for all tool calls (scope parity with UI).
    """
    enabled = await is_assistant_enabled(session)
    if not enabled:
        return JSONResponse(disabled_response(), status_code=200)

    if len(body.question) > 1000:
        raise HTTPException(status_code=422, detail="Question too long (max 1000 characters).")

    role = _user_role(current_user)
    caller_token = _extract_token(request)

    # Get or create session
    session_id = body.session_id or str(uuid.uuid4())
    session_context = await _get_session_context(session, session_id)

    # Data clock
    data_clock = await _get_data_clock(session)

    # Action layer status
    al_enabled = await _check_action_layer_enabled(session)

    # ── Zero-LLM shortcut: capability/help questions ─────────────────────────
    _help_triggers = {
        "what can you do", "what do you do", "help", "capabilities",
        "what questions", "how do you work", "what are you", "who are you",
        "what can i ask", "what topics",
    }
    q_lower = body.question.lower().strip().rstrip("?")
    if any(t in q_lower for t in _help_triggers):
        al_enabled_h = await _check_action_layer_enabled(session)
        catalog = compact_catalog(role, al_enabled_h)
        caps = ", ".join(g["name"] for g in _build_capability_groups(catalog))
        shortcut_answer = {
            "headline": "I answer questions about your conversation data using verified tool results.",
            "details": [
                f"I can help with: {caps}.",
                "Every number comes from a live API call — I never invent figures.",
                "I cannot predict, diagnose causes, or access financial/CSAT data.",
                "Click 'Help' at the top of this page for the full capability guide.",
            ],
            "table": None, "evidence_line": "Source: built-in capability registry",
            "caveats": [], "verification_label": "verified", "checks": [],
            "followups": ["Give me an overview summary", "Which call reasons have the highest unresolved rate?"],
            "page_links": [], "is_fallback": False, "is_out_of_scope": False,
            "is_clarification": False, "data_clock": data_clock, "tools_used": [],
        }
        return JSONResponse({
            "enabled": True, "session_id": session_id,
            "message_id": str(uuid.uuid4()), "answer": shortcut_answer,
            "latency_ms": 0, "steps": [],
        })

    # Build pipeline
    from backend.assistant.llm_adapter import AssistantLLMAdapter
    from backend.assistant.pipeline import AssistantPipeline

    settings_row = await _get_asst_settings(session)
    rate_limit = settings_row.rate_limit_per_user_per_hour if settings_row else 20

    adapter = AssistantLLMAdapter(rate_limit_per_hour=rate_limit)
    pipeline = AssistantPipeline(adapter, data_clock=data_clock)

    t0 = time.perf_counter()
    try:
        from backend.assistant.llm_adapter import LLMBudgetExhaustedError
        answer, steps = await pipeline.run(
            question=body.question,
            role=role,
            caller_token=caller_token,
            action_layer_enabled=al_enabled,
            session_context=session_context,
            ui_context=body.ui_context,
        )
    except LLMBudgetExhaustedError as e:
        rate_answer = {
            "headline": f"Assistant Error: {str(e)}",
            "details": [], "table": None, "evidence_line": "",
            "caveats": [], "verification_label": "could_not_verify", "checks": [],
            "followups": [], "page_links": [], "is_fallback": True,
            "is_out_of_scope": False, "is_clarification": False,
            "data_clock": data_clock, "tools_used": [],
        }
        return JSONResponse({
            "enabled": True, "session_id": session_id,
            "message_id": str(uuid.uuid4()), "answer": rate_answer,
            "latency_ms": 0, "steps": [],
        }, status_code=200)
    except Exception as e:
        return JSONResponse({
            "enabled": True,
            "error": "pipeline_error",
            "message": "The assistant encountered an error. Please try again.",
        }, status_code=500)

    latency_ms = (time.perf_counter() - t0) * 1000

    # Persist message (no tool result bodies)
    msg_id = await _persist_message(
        session=session,
        session_id=session_id,
        user_id=getattr(current_user, "id", 0),
        question=body.question,
        answer=answer,
        latency_ms=latency_ms,
    )

    return JSONResponse({
        "enabled": True,
        "session_id": session_id,
        "message_id": msg_id,
        "answer": _payload_to_dict(answer),
        "steps": steps,
    })


# ── POST /api/v1/assistant/feedback ──────────────────────────────────────────

@router.post("/feedback")
async def assistant_feedback(
    body: FeedbackRequest,
    session: DbSession,
    current_user=Depends(get_current_user),
):
    """Record thumbs up/down feedback for a message."""
    from backend.assistant.models import AsstFeedback
    fb = AsstFeedback(
        message_id=body.message_id,
        rating=body.rating,
        reason=body.reason,
    )
    session.add(fb)
    await session.commit()
    return JSONResponse({"ok": True})


# ── DELETE /api/v1/assistant/session/{session_id}/context ────────────────────

@router.delete("/session/{session_id}/context")
async def clear_session_context(
    session_id: str,
    session: DbSession,
    current_user=Depends(get_current_user),
):
    """Clear resolved context (entities, filters) for a session."""
    from sqlalchemy import select, update
    from backend.assistant.models import AsstSession
    await session.execute(
        update(AsstSession)
        .where(AsstSession.id == session_id,
               AsstSession.user_id == getattr(current_user, "id", 0))
        .values(context_json="{}")
    )
    await session.commit()
    return JSONResponse({"ok": True})


@router.post("/feedback")
async def post_feedback(
    req: FeedbackRequest,
    session: DbSession,
    current_user=Depends(get_current_user),
):
    """Save user feedback for an assistant message."""
    from backend.assistant.models import AsstFeedback
    
    fb = AsstFeedback(
        message_id=req.message_id,
        rating=req.rating,
        reason=req.reason,
    )
    session.add(fb)
    await session.commit()
    return JSONResponse({"ok": True})


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_session_context(session: AsyncSession, session_id: str) -> dict:
    from sqlalchemy import select
    from backend.assistant.models import AsstSession
    import json as _json
    row = (await session.execute(
        select(AsstSession).where(AsstSession.id == session_id)
    )).scalars().first()
    if row is None:
        return {}
    try:
        return _json.loads(row.context_json or "{}")
    except Exception:
        return {}


async def _get_data_clock(session: AsyncSession) -> str:
    from sqlalchemy import select, func
    from backend.models import Conversation
    max_dt = (await session.execute(
        select(func.max(Conversation.started_at))
    )).scalar()
    if max_dt is None:
        return "unknown"
    return str(max_dt)[:10]  # YYYY-MM-DD


async def _check_action_layer_enabled(session: AsyncSession) -> bool:
    from sqlalchemy import select
    from backend.action_layer.models import ActSettings
    try:
        row = (await session.execute(select(ActSettings).limit(1))).scalars().first()
        return bool(row and row.enabled)
    except Exception:
        return False


async def _get_asst_settings(session: AsyncSession):
    from sqlalchemy import select
    from backend.assistant.models import AsstSettings
    return (await session.execute(select(AsstSettings).limit(1))).scalars().first()


async def _persist_message(
    *,
    session: AsyncSession,
    session_id: str,
    user_id: int,
    question: str,
    answer,
    latency_ms: float,
) -> str:
    import json as _json
    from backend.assistant.models import AsstSession, AsstMessage

    # Upsert session
    from sqlalchemy import select, update
    existing = (await session.execute(
        select(AsstSession).where(AsstSession.id == session_id)
    )).scalars().first()
    if existing is None:
        sess_row = AsstSession(id=session_id, user_id=user_id)
        session.add(sess_row)
    else:
        await session.execute(
            update(AsstSession)
            .where(AsstSession.id == session_id)
            .values(last_active_at=__import__("datetime").datetime.utcnow())
        )

    # User message
    user_msg = AsstMessage(
        session_id=session_id,
        role="user",
        content_text=question[:2000],
    )
    session.add(user_msg)

    # Assistant message — store headline only in content_text, full payload in JSON
    asst_msg = AsstMessage(
        session_id=session_id,
        role="assistant",
        content_text=answer.headline[:500],
        answer_payload_json=_json.dumps(dataclasses.asdict(answer), default=str)[:50000],
        verification_label=answer.verification_label,
        checks_json=_json.dumps(answer.checks, default=str),
        tools_used=",".join(answer.tools_used),
        latency_ms=round(latency_ms, 1),
    )
    session.add(asst_msg)
    await session.commit()
    return asst_msg.id
