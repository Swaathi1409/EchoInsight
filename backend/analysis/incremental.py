"""
Per-turn extraction: lightweight LLM call for a single turn.
Called inline during append_turn for incremental provisional state updates.
"""
from __future__ import annotations
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.llm.client import chat_json
from backend.llm.prompts import TURN_EXTRACTION_SCHEMA, build_turn_messages
from backend.validator.evidence_gate import gate_commitments, check_quote
from backend.state.reducer import apply_turn_extraction
from backend.models import Turn

logger = logging.getLogger(__name__)

MAX_PRECEDING = 3  # turns to include as context


async def run_per_turn_extraction(
    conversation_id: str,
    turn_id: str,
    turn_text: str,
    current_state: dict,
    session: AsyncSession,
) -> dict:
    """
    Run per-turn LLM extraction for a single new turn.
    Returns updated provisional state dict.
    Errors are caught and logged; on failure the state is returned unchanged
    with the turn's extraction_status set to indicate failure.
    """
    # Build preceding context (last MAX_PRECEDING turns before this one)
    seq_of_turn = int(turn_id.split("_")[1])
    preceding_rows = (await session.execute(
        select(Turn)
        .where(Turn.conversation_id == conversation_id, Turn.seq < seq_of_turn)
        .order_by(Turn.seq.desc())
        .limit(MAX_PRECEDING)
    )).scalars().all()
    preceding_rows = list(reversed(preceding_rows))

    preceding_text = "\n".join(
        f"[{t.speaker.upper()} | {t.turn_id}] {t.text_redacted}"
        for t in preceding_rows
    )

    # State digest: compact summary of provisional state
    state_digest = _build_state_digest(current_state)

    messages = build_turn_messages(turn_text, turn_id, preceding_text, state_digest)

    try:
        raw, pt, ct = await chat_json(messages, TURN_EXTRACTION_SCHEMA)
        logger.debug("Per-turn extraction %s: prompt=%d completion=%d", turn_id, pt, ct)
    except Exception as exc:
        logger.warning("Per-turn extraction failed for %s: %s", turn_id, exc)
        # Return state unchanged; caller marks extraction_status=failed
        return current_state, False

    # Evidence gate: validate any commitment quotes against the current turn
    turns_by_id = {t.turn_id: t.text_redacted for t in preceding_rows}
    turns_by_id[turn_id] = turn_text

    gated_new_commitments = []
    for c in raw.get("new_commitments", []):
        quote = c.get("quote", "")
        ref_turn = c.get("turn_id", turn_id)
        ref_text = turns_by_id.get(ref_turn, turn_text)
        if quote and not check_quote(quote, ref_text):
            c = {**c, "needs_review": True, "evidence_flag": "quote_mismatch"}
        gated_new_commitments.append(c)
    raw["new_commitments"] = gated_new_commitments

    # Apply reducer
    updated_state = apply_turn_extraction(current_state, raw, turn_id, turn_text)
    updated_state["provisional"] = True
    return updated_state, True


def _build_state_digest(state: dict) -> str:
    """Compact, token-efficient digest of the current provisional state."""
    resolution = state.get("resolution", "unknown")
    sentiment = state.get("sentiment_current", "neutral")
    churn = state.get("churn_risk", "low")
    open_commitments = [
        c["description"][:60]
        for c in state.get("commitments", [])
        if c.get("status") not in ("completed", "cancelled")
    ]
    parts = [f"resolution={resolution}", f"sentiment={sentiment}", f"churn_risk={churn}"]
    if open_commitments:
        parts.append(f"open_commitments={open_commitments}")
    return "; ".join(parts)
