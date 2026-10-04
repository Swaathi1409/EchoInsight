"""
backend/assistant/llm_adapter.py
Wraps the existing chat_json LLM client for assistant use.
Adds per-user rate limiting, budget guard, and token tracking.
Tests use MockLLMAdapter labeled 'mock'.
"""
from __future__ import annotations

import collections
import time
from typing import Any


class LLMBudgetExhaustedError(Exception):
    """Raised when the token budget or rate limit is exhausted."""


class AssistantLLMAdapter:
    """
    Production adapter. Calls the existing chat_json via the existing budget guard.
    Adds per-user rate limiting (configurable, default 20 calls/hour).
    """

    def __init__(self, rate_limit_per_hour: int = 20):
        self._rate_limit = rate_limit_per_hour
        # user_id -> deque of call timestamps
        self._user_calls: dict[int, collections.deque] = collections.defaultdict(
            lambda: collections.deque()
        )

    def _check_rate_limit(self, user_id: int) -> None:
        now = time.time()
        window_start = now - 3600
        dq = self._user_calls[user_id]
        # Remove calls older than 1 hour
        while dq and dq[0] < window_start:
            dq.popleft()
        if len(dq) >= self._rate_limit:
            raise LLMBudgetExhaustedError(
                f"Rate limit reached: {self._rate_limit} calls/hour per user."
            )
        dq.append(now)

    async def complete(
        self,
        prompt: str,
        max_tokens: int = 1200,
        json_mode: bool = True,
        user_id: int | None = None,
    ) -> str:
        """
        Send a prompt and return the raw response string.
        Uses the existing chat_json with a generic JSON schema.
        """
        if user_id is not None:
            self._check_rate_limit(user_id)

        from backend.llm.client import chat_json
        from backend.llm.budget import BudgetExceededError

        try:
            result, _pt, _ct = await chat_json(
                messages=[{"role": "user", "content": prompt}],
                schema=_generic_schema(),
                temperature=0.0,
            )
        except BudgetExceededError as e:
            raise LLMBudgetExhaustedError(str(e)) from e

        import json
        return json.dumps(result)


def _generic_schema() -> dict[str, Any]:
    """Permissive schema: accept any JSON object."""
    return {"type": "object", "additionalProperties": True}


class MockLLMAdapter:
    """
    MOCK: deterministic test double. Label: 'mock'.
    Used in tests only. Programmed via response_queue.
    """

    def __init__(self, responses: list[str] | None = None):
        self._responses = list(responses or [])
        self.calls: list[str] = []

    def queue(self, *responses: str) -> None:
        self._responses.extend(responses)

    async def complete(
        self,
        prompt: str,
        max_tokens: int = 1200,
        json_mode: bool = True,
        user_id: int | None = None,
    ) -> str:
        self.calls.append(prompt[:200])  # record truncated prompt for assertions
        if not self._responses:
            raise RuntimeError("MockLLMAdapter: response queue is empty")
        return self._responses.pop(0)
