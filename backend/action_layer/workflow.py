"""
backend/action_layer/workflow.py
Workflow state machine for ActItem transitions.

Valid transitions:
  new       → claimed       (any authenticated user)
  claimed   → contacted     (assignee or admin)
  contacted → recovered     (assignee or admin)
  contacted → lost          (assignee or admin)
  contacted → dismissed     (assignee or admin, requires reason)
  claimed   → dismissed     (assignee or admin, requires reason)
  new       → dismissed     (supervisor/admin, requires reason)
  recovered | lost → claimed (supervisor/admin reopen with reason)
  dismissed → claimed       (supervisor/admin reopen with reason)

Rules:
- dismissed always requires a reason.
- reopen (any closed state → claimed) requires supervisor or admin role and a reason.
- Each transition writes an ActItemEvent and an audit log entry.
- No writes to core tables.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.action_layer.models import ActItem, ActItemEvent
from backend.models import AuditLog

logger = structlog.get_logger(__name__)

# Allowed transitions: {from_status: set of allowed to_statuses}
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "new":       {"claimed", "dismissed"},
    "claimed":   {"contacted", "dismissed"},
    "contacted": {"recovered", "lost", "dismissed"},
    # Reopen: supervisor/admin only
    "recovered": {"claimed"},
    "lost":      {"claimed"},
    "dismissed": {"claimed"},
}

# Statuses that require a dismissal reason
REQUIRES_REASON = {"dismissed"}

# Statuses that require supervisor or admin role to transition FROM
REQUIRES_SUPERVISOR_FROM = {"recovered", "lost", "dismissed"}

# Human-readable status labels
STATUS_LABELS = {
    "new": "New",
    "claimed": "Claimed",
    "contacted": "Contacted",
    "recovered": "Recovered",
    "lost": "Lost",
    "dismissed": "Dismissed",
}

OUTCOME_VALUES = {"retained", "left", "no_response", "unknown", None}


class WorkflowError(Exception):
    """Raised when a workflow transition is invalid."""
    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(detail)


async def transition_item(
    *,
    item_id: int,
    to_status: str,
    actor_user_id: int,
    actor_role: str,
    session: AsyncSession,
    notes: str = "",
    outcome: str | None = None,
    dismissal_reason: str | None = None,
) -> dict[str, Any]:
    """
    Execute a workflow transition on an ActItem.
    Returns the updated item as a dict.
    Raises WorkflowError on invalid transitions.
    """
    item = (await session.execute(
        select(ActItem).where(ActItem.id == item_id, ActItem.current == True)
    )).scalars().first()

    if item is None:
        raise WorkflowError("not_found", f"ActItem {item_id} not found or not current")

    from_status = item.status

    # ── Validate transition ────────────────────────────────────────────────────
    allowed = ALLOWED_TRANSITIONS.get(from_status, set())
    if to_status not in allowed:
        raise WorkflowError(
            "invalid_transition",
            f"Cannot transition from '{STATUS_LABELS.get(from_status, from_status)}' "
            f"to '{STATUS_LABELS.get(to_status, to_status)}'. "
            f"Allowed: {[STATUS_LABELS.get(s, s) for s in sorted(allowed)]}",
        )

    # ── Supervisor/admin required for reopening ───────────────────────────────
    if from_status in REQUIRES_SUPERVISOR_FROM:
        if actor_role not in ("admin", "supervisor"):
            raise WorkflowError(
                "permission_denied",
                f"Only supervisors or admins can reopen from '{STATUS_LABELS[from_status]}'.",
            )

    # ── Dismissal requires a reason ───────────────────────────────────────────
    if to_status in REQUIRES_REASON:
        if not dismissal_reason or not dismissal_reason.strip():
            raise WorkflowError(
                "reason_required",
                "A reason is required when dismissing an item.",
            )
        # Reopen: also needs a reason
    if from_status in REQUIRES_SUPERVISOR_FROM:
        if not notes or not notes.strip():
            raise WorkflowError(
                "reason_required",
                "A reason (notes) is required when reopening a closed item.",
            )

    # ── Validate outcome value ────────────────────────────────────────────────
    if outcome is not None and outcome not in (OUTCOME_VALUES - {None}):
        raise WorkflowError(
            "invalid_outcome",
            f"Outcome must be one of: retained, left, no_response, unknown.",
        )

    # ── Apply transition ──────────────────────────────────────────────────────
    item.status = to_status
    if actor_role in ("admin", "supervisor", "agent"):
        item.assignee_user_id = actor_user_id
    if dismissal_reason:
        item.dismissal_reason = dismissal_reason.strip()

    # ── Record event ──────────────────────────────────────────────────────────
    event_type = _event_type_for(from_status, to_status)
    event = ActItemEvent(
        item_id=item.id,
        event_type=event_type,
        from_status=from_status,
        to_status=to_status,
        actor_user_id=actor_user_id,
        notes=notes.strip() if notes else "",
        outcome=outcome,
        payload_json={
            "dismissal_reason": dismissal_reason,
        } if dismissal_reason else {},
    )
    session.add(event)

    # ── Audit log ─────────────────────────────────────────────────────────────
    audit = AuditLog(
        user_id=actor_user_id,
        action=f"action_layer_{event_type}",
        resource_type="act_item",
        resource_id=str(item.id),
        details_json={
            "from_status": from_status,
            "to_status": to_status,
            "conversation_id": item.conversation_id,
            "outcome": outcome,
        },
    )
    session.add(audit)

    await session.flush()

    logger.info(
        "action_layer.workflow_transition",
        item_id=item_id,
        from_status=from_status,
        to_status=to_status,
        actor_user_id=actor_user_id,
    )

    return {
        "item_id": item.id,
        "from_status": from_status,
        "to_status": to_status,
        "event_type": event_type,
    }


def _event_type_for(from_status: str, to_status: str) -> str:
    if to_status == "claimed":
        return "reopened" if from_status in ("recovered", "lost", "dismissed") else "claim"
    if to_status == "contacted":
        return "contact_logged"
    if to_status in ("recovered", "lost"):
        return "outcome_recorded"
    if to_status == "dismissed":
        return "dismissed"
    return "status_changed"
