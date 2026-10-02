"""
Final analysis pipeline: build transcript, call LLM, gate evidence, score QA, persist.
"""
from __future__ import annotations
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.llm.client import chat_json
from backend.llm.prompts import (
    FINAL_ANALYSIS_SCHEMA, QA_SCHEMA,
    build_final_messages, build_qa_messages,
)
from backend.validator.evidence_gate import gate_commitments, gate_qa_items
from backend.qa.scorer import score as qa_score
from backend.models import Analysis, Conversation, QAResult, Turn, Commitment
from backend.config.settings import get_settings

logger = logging.getLogger(__name__)
PROMPT_VERSION = "v1"
POLICY_VERSION = "example_v1"


def _build_transcript(turns: list[Turn]) -> tuple[str, dict[str, str]]:
    """Return (full_text, turns_by_id)."""
    lines = [f"[{t.speaker.upper()} | {t.turn_id}] {t.text_redacted}" for t in turns]
    turns_by_id = {t.turn_id: t.text_redacted for t in turns}
    return "\n".join(lines), turns_by_id


async def run_final_analysis(conversation_id: str, session: AsyncSession) -> str:
    """Run full analysis for a conversation. Returns analysis_id."""
    s = get_settings()

    # Load turns
    result = await session.execute(
        select(Turn).where(Turn.conversation_id == conversation_id).order_by(Turn.seq)
    )
    turns = list(result.scalars())
    if not turns:
        raise ValueError(f"No turns for conversation {conversation_id}")

    transcript, turns_by_id = _build_transcript(turns)

    # Main analysis call
    analysis_messages = build_final_messages(transcript)
    raw, pt, ct = await chat_json(analysis_messages, FINAL_ANALYSIS_SCHEMA)
    logger.info("Final analysis LLM call: prompt=%d completion=%d", pt, ct)

    # Gate commitments
    gated_commitments = gate_commitments(raw.get("commitments", []), turns_by_id)

    # QA call
    qa_messages = build_qa_messages(transcript)
    qa_raw, qa_pt, qa_ct = await chat_json(qa_messages, QA_SCHEMA)
    logger.info("QA LLM call: prompt=%d completion=%d", qa_pt, qa_ct)

    qa_items_gated = gate_qa_items(qa_raw.get("items", []), turns_by_id, transcript)
    qa_result_data = qa_score(qa_items_gated)

    # Persist analysis
    conv_result = await session.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conv = conv_result.scalar_one()
    version = conv.analysis_version + 1

    analysis_id = str(uuid.uuid4())
    analysis = Analysis(
        analysis_id=analysis_id,
        conversation_id=conversation_id,
        version=version,
        provisional=False,
        model=s.llm_primary_model,
        prompt_version=PROMPT_VERSION,
        policy_version=POLICY_VERSION,
        taxonomy_version=1,
        summary=raw.get("summary", ""),
        reasons_json=raw.get("reasons", []),
        resolution=raw.get("resolution", "unknown"),
        churn_risk=raw.get("churn_risk", "low"),
        churn_signals_json=raw.get("churn_signals", []),
        sentiment_trajectory_json=raw.get("sentiment_trajectory", []),
        false_resolution=raw.get("false_resolution", False),
        false_resolution_reason=raw.get("false_resolution_reason", ""),
        prompt_tokens=pt + qa_pt,
        completion_tokens=ct + qa_ct,
    )
    session.add(analysis)

    # Persist QA result
    qa_result = QAResult(
        qa_result_id=qa_result_data["qa_result_id"],
        analysis_id=analysis_id,
        conversation_id=conversation_id,
        analysis_version=version,
        checklist_version=POLICY_VERSION,
        score=qa_result_data["score"],
        score_label=qa_result_data["score_label"],
        coverage=qa_result_data["coverage"],
        items_applicable=qa_result_data["items_applicable"],
        items_assessed=qa_result_data["items_assessed"],
        items_needs_review=qa_result_data["items_needs_review"],
        critical_violation=qa_result_data["critical_violation"],
        items_json=qa_result_data["items"],
    )
    session.add(qa_result)

    # Persist commitments
    for c in gated_commitments:
        commitment = Commitment(
            commitment_id=c.get("commitment_id", str(uuid.uuid4())),
            conversation_id=conversation_id,
            description=c.get("description", ""),
            owner=c.get("owner", ""),
            deadline=c.get("deadline", ""),
            deadline_flag=c.get("deadline_flag", ""),
            status=c.get("status", "proposed"),
            provisional=False,
            created_at_turn_id=c.get("turn_id", turns[0].turn_id),
            evidence_json=c.get("evidence", []),
        )
        session.add(commitment)

    # Update conversation version
    conv.analysis_version = version
    await session.flush()
    return analysis_id
