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
WINDOW_SIZE = 40
WINDOW_OVERLAP = 5


def _build_transcript(turns: list[Turn]) -> tuple[str, dict[str, str]]:
    """Return (full_text, turns_by_id)."""
    lines = [f"[{t.speaker.upper()} | {t.turn_id}] {t.text_redacted}" for t in turns]
    turns_by_id = {t.turn_id: t.text_redacted for t in turns}
    return "\n".join(lines), turns_by_id


def _chunk_turns(turns: list[Turn], window: int = WINDOW_SIZE, overlap: int = WINDOW_OVERLAP) -> list[list[Turn]]:
    """Split turns into overlapping windows for long-call processing."""
    if len(turns) <= window:
        return [turns]
    chunks = []
    step = window - overlap
    i = 0
    while i < len(turns):
        chunks.append(turns[i:i + window])
        i += step
    return chunks


async def _extract_windowed(turns: list[Turn], s) -> tuple[dict, int, int]:
    """
    For long calls: extract per window and merge results by turn_id.
    Returns (merged_raw, total_prompt_tokens, total_completion_tokens).
    """
    chunks = _chunk_turns(turns)
    merged = {
        "summary": "",
        "reasons": [],
        "resolution": "unknown",
        "churn_risk": "low",
        "churn_signals": [],
        "sentiment_trajectory": [],
        "false_resolution": False,
        "false_resolution_reason": "",
        "commitments": [],
    }
    total_pt = total_ct = 0
    seen_turn_ids: set[str] = set()

    for chunk in chunks:
        chunk_text, _ = _build_transcript(chunk)
        messages = build_final_messages(chunk_text)
        raw, pt, ct = await chat_json(messages, FINAL_ANALYSIS_SCHEMA)
        total_pt += pt
        total_ct += ct

        # Merge sentiment_trajectory (deduplicate by turn_id)
        for sp in raw.get("sentiment_trajectory", []):
            if sp.get("turn_id") not in seen_turn_ids:
                merged["sentiment_trajectory"].append(sp)
                seen_turn_ids.add(sp.get("turn_id", ""))

        # Merge churn signals
        merged["churn_signals"] = list(set(merged["churn_signals"] + raw.get("churn_signals", [])))

        # Merge reasons (deduplicate)
        merged["reasons"] = list(set(merged["reasons"] + raw.get("reasons", [])))

        # Take the last window's resolution and churn_risk as most current
        merged["resolution"] = raw.get("resolution", merged["resolution"])
        merged["churn_risk"] = raw.get("churn_risk", merged["churn_risk"])

        # Merge commitments (deduplicate by description)
        existing_descs = {c["description"] for c in merged["commitments"]}
        for c in raw.get("commitments", []):
            if c.get("description") not in existing_descs:
                merged["commitments"].append(c)
                existing_descs.add(c["description"])

        # False resolution: any window detecting it counts
        if raw.get("false_resolution"):
            merged["false_resolution"] = True
            merged["false_resolution_reason"] = raw.get("false_resolution_reason", "")

    # Build summary from first + last turns only
    first_turns, _ = _build_transcript(turns[:3])
    last_turns, _ = _build_transcript(turns[-3:])
    summary_messages = build_final_messages(
        f"[First 3 turns]\n{first_turns}\n\n[Last 3 turns]\n{last_turns}\n\n"
        f"[Merged reasons: {merged['reasons']}]\n[Resolution: {merged['resolution']}]"
    )
    try:
        summary_raw, spt, sct = await chat_json(summary_messages, FINAL_ANALYSIS_SCHEMA)
        total_pt += spt
        total_ct += sct
        merged["summary"] = summary_raw.get("summary", merged["summary"])
    except Exception:
        merged["summary"] = f"Long call ({len(turns)} turns). Resolution: {merged['resolution']}."

    return merged, total_pt, total_ct


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

    # Route: use windowed extraction for long calls (>40 turns)
    if len(turns) > WINDOW_SIZE:
        logger.info("Long call (%d turns): using windowed extraction", len(turns))
        raw, pt, ct = await _extract_windowed(turns, s)
    else:
        analysis_messages = build_final_messages(transcript)
        raw, pt, ct = await chat_json(analysis_messages, FINAL_ANALYSIS_SCHEMA)
        logger.info("Final analysis LLM call: prompt=%d completion=%d", pt, ct)

    # Gate commitments
    gated_commitments = gate_commitments(raw.get("commitments", []), turns_by_id)

    # QA call (truncate to last 40 turns for very long transcripts)
    if len(turns) > WINDOW_SIZE:
        qa_transcript, _ = _build_transcript(turns[-WINDOW_SIZE:])
    else:
        qa_transcript = transcript
    qa_messages = build_qa_messages(qa_transcript)
    qa_raw, qa_pt, qa_ct = await chat_json(qa_messages, QA_SCHEMA)
    logger.info("QA LLM call: prompt=%d completion=%d", qa_pt, qa_ct)

    qa_items_gated = gate_qa_items(qa_raw.get("items", []), turns_by_id, transcript)

    # Phrase matcher augmentation: override/augment LLM QA results with
    # deterministic keyword checks for prohibited_promises, greeting, closure.
    turns_list = [{"turn_id": t.turn_id, "speaker": t.speaker, "text": t.text_redacted} for t in turns]
    try:
        from backend.qa.phrase_matcher import (
            check_prohibited_promises, check_greeting,
            check_identity_verification, check_closure
        )
        phrase_overrides = {
            "prohibited_promises": check_prohibited_promises(turns_list),
            "greeting": check_greeting(turns_list),
            "identity_verification": check_identity_verification(turns_list),
            "closure": check_closure(turns_list),
        }
        for item in qa_items_gated:
            pid = item.get("item_id", "")
            pm = phrase_overrides.get(pid)
            if pm is not None and pm.matched:
                # Phrase matcher found a definitive signal; upgrade confidence
                if pid == "prohibited_promises" and item.get("result") != "fail":
                    # Deterministic violation detected — override to fail
                    item["result"] = "fail"
                    item["confidence"] = 1.0
                    item["explanation"] = f"Prohibited phrase detected: '{pm.phrase}'"
                    item["quote"] = pm.quote
                    item["turn_id"] = pm.turn_id
                elif pid in ("greeting", "identity_verification", "closure"):
                    if item.get("result") in ("fail", "needs_review"):
                        # Phrase matcher found it; override to pass
                        item["result"] = "pass"
                        item["confidence"] = max(item.get("confidence", 0.8), 0.9)
                        item["quote"] = item.get("quote") or pm.quote
                        item["turn_id"] = item.get("turn_id") or pm.turn_id
    except Exception as exc:
        logger.warning("Phrase matcher augmentation failed: %s", exc)

    # Selective verification: second LLM call for high-risk/ambiguous items
    open_commitments = [
        c for c in raw.get("commitments", [])
        if c.get("status") not in ("completed", "cancelled")
    ]
    try:
        from backend.qa.verification import run_selective_verification
        qa_items_verified = await run_selective_verification(
            qa_items_gated, turns_by_id, turns_list,
            open_commitments, raw.get("resolution", "unknown")
        )
    except Exception as exc:
        logger.warning("Selective verification failed: %s", exc)
        qa_items_verified = qa_items_gated

    qa_result_data = qa_score(qa_items_verified)

    # Validator hard gate: all 7 conditions must pass
    try:
        from backend.validator.hard_gate import validate_analysis, log_validation_errors
        gate_result = validate_analysis(raw, turns_by_id, qa_items_verified)
        log_validation_errors(gate_result, conversation_id)
        if not gate_result.passed:
            # Mark critical items needs_review; persist with a note
            logger.warning(
                "Hard gate failed for %s: %d error(s). Marking needs_review.",
                conversation_id, len(gate_result.errors)
            )
            # Flag all QA items as needs_review if gate fails
            for item in qa_items_verified:
                if item.get("result") in ("pass", "fail"):
                    item["human_review_required"] = True
    except Exception as exc:
        logger.warning("Hard gate check failed with exception: %s", exc)

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
