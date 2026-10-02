"""
Evidence gate: verify every LLM claim has an exact-quote match in the redacted transcript.
"""
from __future__ import annotations
import re


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def check_quote(quote: str, turn_text: str) -> bool:
    """Return True if quote (non-empty) is an exact substring of turn_text (case-insensitive, whitespace-normalized)."""
    if not quote or len(quote) < 3:
        return True  # empty/short quote: not blocked, flagged elsewhere
    return _normalize(quote) in _normalize(turn_text)


def gate_commitments(commitments: list[dict], turns_by_id: dict[str, str]) -> list[dict]:
    """
    Filter commitment list through the evidence gate.
    Commitments with a failing quote are flagged needs_review=True.
    """
    result = []
    for c in commitments:
        turn_id = c.get("turn_id", "")
        quote = c.get("quote", "")
        turn_text = turns_by_id.get(turn_id, "")
        if quote and turn_id and not check_quote(quote, turn_text):
            c = {**c, "needs_review": True, "evidence_flag": "quote_mismatch"}
        else:
            c = {**c, "needs_review": False}
        result.append(c)
    return result


def gate_qa_items(items: list[dict], turns_by_id: dict[str, str], full_text: str) -> list[dict]:
    """
    Validate QA item quotes against the turn they reference.
    Falls back to full transcript search if turn_id is empty.
    """
    result = []
    for item in items:
        quote = item.get("quote", "")
        turn_id = item.get("turn_id", "")
        search_text = turns_by_id.get(turn_id, full_text) if turn_id else full_text
        if quote and not check_quote(quote, search_text):
            item = {**item, "result": "needs_review", "human_review_required": True,
                    "evidence_flag": "quote_mismatch"}
        result.append(item)
    return result
