"""
Daily LLM token budget enforcer.

Tracks prompt+completion tokens consumed today (UTC day).
Raises BudgetExceededError when the daily budget is exhausted.
Uses an in-process counter with a date key — reset happens automatically
when the UTC day rolls over.

For production: replace with a Redis INCR + EXPIRE or DB counter.
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# In-process state
_budget_state: dict = {"date": "", "used": 0}


class BudgetExceededError(Exception):
    """Raised when the daily token budget is exhausted."""
    def __init__(self, used: int, limit: int):
        self.used = used
        self.limit = limit
        super().__init__(f"Daily token budget exceeded: used {used} of {limit}")


def _today_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _reset_if_new_day() -> None:
    today = _today_utc()
    if _budget_state["date"] != today:
        _budget_state["date"] = today
        _budget_state["used"] = 0
        logger.info("Token budget reset for new day: %s", today)


def check_and_record(prompt_tokens: int, completion_tokens: int, budget_limit: int) -> None:
    """
    Check that budget is not exceeded, then record the tokens used.
    Call AFTER a successful LLM call.
    Raises BudgetExceededError if would exceed limit.
    """
    _reset_if_new_day()
    total = prompt_tokens + completion_tokens
    _budget_state["used"] += total
    if _budget_state["used"] > budget_limit:
        logger.warning(
            "Daily token budget exceeded: used=%d limit=%d",
            _budget_state["used"], budget_limit
        )
        raise BudgetExceededError(_budget_state["used"], budget_limit)


def check_budget(budget_limit: int) -> None:
    """Pre-flight check before making an LLM call."""
    _reset_if_new_day()
    if _budget_state["used"] >= budget_limit:
        raise BudgetExceededError(_budget_state["used"], budget_limit)


def get_budget_status(budget_limit: int) -> dict:
    """Return current budget usage stats."""
    _reset_if_new_day()
    used = _budget_state["used"]
    return {
        "date": _budget_state["date"],
        "used": used,
        "limit": budget_limit,
        "remaining": max(0, budget_limit - used),
        "pct_used": round(used / budget_limit * 100, 1) if budget_limit else 0,
    }
