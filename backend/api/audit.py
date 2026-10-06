"""
Audit log helper: append-only write utility.

Every protected state-changing action (login, create conversation, end conversation,
update commitment, admin checklist change) should call audit_log() with the
authenticated user, action name, resource type and ID, and any relevant detail.

The audit log is never modified or deleted. Purge is a separate retention operation.
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import AuditLog

logger = logging.getLogger(__name__)


async def audit_log(
    session: AsyncSession,
    *,
    user_id: int | None,
    action: str,
    resource_type: str,
    resource_id: str,
    details: dict[str, Any] | None = None,
) -> None:
    """
    Append an audit log entry.
    Failures are logged but never raised — audit must not block the main operation.
    """
    try:
        entry = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details_json=details or {},
        )
        session.add(entry)
        # Do not flush here — caller's transaction will commit it together
    except Exception as exc:
        logger.warning("Audit log write failed: %s", exc)
