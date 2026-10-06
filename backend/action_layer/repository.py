"""
backend/action_layer/repository.py
Read-only access to core tables for the Action Intelligence Layer.

This module NEVER writes to core tables. All writes go to act_* tables.
Uses the existing get_db_session from backend.db — no separate session factory needed.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import (
    Agent,
    Analysis,
    Case,
    CaseConversation,
    Commitment,
    Conversation,
    QAResult,
    Turn,
)


class CoreRepository:
    """
    Read-only queries against core tables.
    All methods accept an AsyncSession and return plain dicts or typed values.
    No ORM objects leave this class to prevent accidental writes.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    # ── Conversation + Analysis ───────────────────────────────────────────────

    async def get_final_analysis(self, conversation_id: str) -> dict[str, Any] | None:
        """Return the latest non-provisional analysis for a conversation."""
        row = (await self._s.execute(
            select(Analysis)
            .where(Analysis.conversation_id == conversation_id,
                   Analysis.provisional == False)
            .order_by(Analysis.version.desc())
            .limit(1)
        )).scalars().first()
        if row is None:
            return None
        return self._analysis_to_dict(row)

    async def get_conversation(self, conversation_id: str) -> dict[str, Any] | None:
        row = (await self._s.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )).scalars().first()
        if row is None:
            return None
        return {
            "id": row.id,
            "source_id": row.source_id,
            "agent_id": row.agent_id,
            "team_id": row.team_id,
            "channel": row.channel,
            "status": row.status,
            "started_at": row.started_at,
            "ended_at": row.ended_at,
        }

    async def list_analyzed_conversations(
        self, *, team_id: str | None = None, agent_id: str | None = None,
        limit: int = 500, offset: int = 0
    ) -> list[dict[str, Any]]:
        """Return conversations with latest final analysis + QA score (left-joined)."""
        # Subquery: latest analysis version per conversation
        latest_subq = (
            select(
                Analysis.conversation_id,
                func.max(Analysis.version).label("max_version")
            )
            .where(Analysis.provisional == False)
            .group_by(Analysis.conversation_id)
            .subquery()
        )
        q = (
            select(Conversation, Analysis, QAResult)
            .join(Analysis, Analysis.conversation_id == Conversation.id)
            .join(latest_subq,
                  (latest_subq.c.conversation_id == Analysis.conversation_id) &
                  (latest_subq.c.max_version == Analysis.version))
            .outerjoin(QAResult, QAResult.conversation_id == Conversation.id)
            .where(Analysis.provisional == False)
        )
        if team_id:
            q = q.where(Conversation.team_id == team_id)
        if agent_id:
            q = q.where(Conversation.agent_id == agent_id)
        q = q.offset(offset).limit(limit)

        rows = (await self._s.execute(q)).all()
        return [
            {
                **self._analysis_to_dict(r.Analysis),
                "qa_score": r.QAResult.score if r.QAResult is not None else None,
                "conversation": {
                    "id": r.Conversation.id,
                    "source_id": r.Conversation.source_id,
                    "agent_id": r.Conversation.agent_id,
                    "team_id": r.Conversation.team_id,
                    "started_at": r.Conversation.started_at,
                    "ended_at": r.Conversation.ended_at,
                    "channel": r.Conversation.channel,
                },
            }
            for r in rows
        ]

    # ── Commitments ───────────────────────────────────────────────────────────

    async def get_commitments(self, conversation_id: str) -> list[dict[str, Any]]:
        rows = (await self._s.execute(
            select(Commitment)
            .where(Commitment.conversation_id == conversation_id,
                   Commitment.provisional == False)
        )).scalars().all()
        return [self._commitment_to_dict(r) for r in rows]

    async def get_open_commitments(self, conversation_id: str) -> list[dict[str, Any]]:
        rows = (await self._s.execute(
            select(Commitment)
            .where(Commitment.conversation_id == conversation_id,
                   Commitment.provisional == False,
                   Commitment.status.notin_(["completed", "cancelled"]))
        )).scalars().all()
        return [self._commitment_to_dict(r) for r in rows]

    # ── QA Results ────────────────────────────────────────────────────────────

    async def get_qa_result(self, conversation_id: str) -> dict[str, Any] | None:
        row = (await self._s.execute(
            select(QAResult)
            .where(QAResult.conversation_id == conversation_id)
            .order_by(QAResult.created_at.desc())
            .limit(1)
        )).scalars().first()
        if row is None:
            return None
        return {
            "qa_result_id": row.qa_result_id,
            "conversation_id": row.conversation_id,
            "score": row.score,
            "score_label": row.score_label,
            "coverage": row.coverage,
            "critical_violation": row.critical_violation,
            "items_json": row.items_json,
            "checklist_version": row.checklist_version,
        }

    # ── Turns ─────────────────────────────────────────────────────────────────

    async def get_turns(self, conversation_id: str) -> list[dict[str, Any]]:
        rows = (await self._s.execute(
            select(Turn)
            .where(Turn.conversation_id == conversation_id)
            .order_by(Turn.seq)
        )).scalars().all()
        return [
            {
                "turn_id": r.turn_id,
                "seq": r.seq,
                "speaker": r.speaker,
                "text_redacted": r.text_redacted,
                "timestamp": r.timestamp,
            }
            for r in rows
        ]

    async def get_turn_by_id(
        self, conversation_id: str, turn_id: str
    ) -> dict[str, Any] | None:
        row = (await self._s.execute(
            select(Turn)
            .where(Turn.conversation_id == conversation_id, Turn.turn_id == turn_id)
        )).scalars().first()
        if row is None:
            return None
        return {
            "turn_id": row.turn_id,
            "seq": row.seq,
            "speaker": row.speaker,
            "text_redacted": row.text_redacted,
        }

    # ── Cases (repeat contact detection) ─────────────────────────────────────

    async def get_cases_for_conversation(
        self, conversation_id: str
    ) -> list[dict[str, Any]]:
        rows = (await self._s.execute(
            select(Case, CaseConversation)
            .join(CaseConversation, CaseConversation.case_id == Case.case_id)
            .where(CaseConversation.conversation_id == conversation_id)
        )).all()
        return [
            {
                "case_id": r.Case.case_id,
                "status": r.Case.status,
                "title": r.Case.title,
                "created_at": r.Case.created_at,
            }
            for r in rows
        ]

    async def get_conversations_in_case(self, case_id: str) -> list[str]:
        """Return all conversation IDs linked to this case (for repeat-contact detection)."""
        rows = (await self._s.execute(
            select(CaseConversation.conversation_id)
            .where(CaseConversation.case_id == case_id)
        )).scalars().all()
        return list(rows)

    # ── Agent / Team lookups ──────────────────────────────────────────────────

    async def get_agent(self, agent_id: str) -> dict[str, Any] | None:
        row = (await self._s.execute(
            select(Agent).where(Agent.agent_id == agent_id)
        )).scalars().first()
        if row is None:
            return None
        return {
            "agent_id": row.agent_id,
            "display_name": row.display_name,
            "team_id": row.team_id,
            "synthetic_assignment": row.synthetic_assignment,
        }

    # ── Dataset as-of clock ───────────────────────────────────────────────────

    async def get_max_started_at(self) -> datetime | None:
        """Return the latest started_at across all conversations (dataset clock)."""
        return (await self._s.execute(
            select(func.max(Conversation.started_at))
            .where(Conversation.started_at.isnot(None))
        )).scalar()

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _analysis_to_dict(row: Analysis) -> dict[str, Any]:
        return {
            "analysis_id": row.analysis_id,
            "conversation_id": row.conversation_id,
            "version": row.version,
            "resolution": row.resolution,
            "churn_risk": row.churn_risk,
            "churn_signals": row.churn_signals_json,
            "sentiment_trajectory": row.sentiment_trajectory_json,
            "false_resolution": row.false_resolution,
            "false_resolution_reason": row.false_resolution_reason,
            "reasons": row.reasons_json,
            "summary": row.summary,
            "prompt_version": row.prompt_version,
        }

    @staticmethod
    def _commitment_to_dict(row: Commitment) -> dict[str, Any]:
        return {
            "commitment_id": row.commitment_id,
            "description": row.description,
            "owner": row.owner,
            "deadline": row.deadline,
            "deadline_flag": row.deadline_flag,
            "status": row.status,
            "evidence_json": row.evidence_json,
            "created_at_turn_id": row.created_at_turn_id,
        }
