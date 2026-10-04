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
        Send a prompt and return raw JSON string.
        Uses Groq with response_format=json_object (no strict schema)
        to avoid the additionalProperties:false Groq restriction.
        Budget-guarded via the existing budget module.
        """
        if user_id is not None:
            self._check_rate_limit(user_id)

        from backend.llm.budget import check_budget, check_and_record, BudgetExceededError
        from backend.llm.client import get_client
        from backend.config.settings import get_settings

        s = get_settings()
        try:
            check_budget(s.llm_daily_token_budget)
        except BudgetExceededError as e:
            raise LLMBudgetExhaustedError(str(e)) from e

        import asyncio, re as _re
        from openai import AsyncOpenAI

        # Prefer OpenRouter when key is configured
        if s.openrouter_api_key:
            llm_client = AsyncOpenAI(
                api_key=s.openrouter_api_key,
                base_url="https://openrouter.ai/api/v1",
            )
            model_name = s.openrouter_model
        elif s.gemini_api_key:
            llm_client = AsyncOpenAI(
                api_key=s.gemini_api_key,
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            )
            model_name = s.gemini_model
        else:
            from backend.llm.client import get_client
            llm_client = get_client()
            model_name = s.llm_primary_model

        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                resp = await llm_client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.0,
                    response_format={"type": "json_object"},
                    max_tokens=max_tokens,
                )
                last_exc = None
                break
            except Exception as e:
                last_exc = e
                msg = str(e)
                if "429" in msg or "rate_limit" in msg.lower() or "quota" in msg.lower():
                    m = _re.search(r"try again in (\d+\.?\d*)s", msg, _re.IGNORECASE)
                    wait = float(m.group(1)) + 1.0 if m else (5.0 * (attempt + 1))
                    await asyncio.sleep(min(wait, 30.0))
                else:
                    break

        if last_exc is not None:
            raise LLMBudgetExhaustedError(f"LLM call failed: {last_exc}") from last_exc

        usage = resp.usage
        pt = usage.prompt_tokens if usage else 0
        ct = usage.completion_tokens if usage else 0
        try:
            check_and_record(pt, ct, s.llm_daily_token_budget)
        except BudgetExceededError:
            pass

        import json
        content = resp.choices[0].message.content or "{}"
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        elif content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        # Ensure we always return a JSON object string
        try:
            parsed = json.loads(content)
            if not isinstance(parsed, dict):
                content = json.dumps({"result": parsed})
        except json.JSONDecodeError:
            pass
        return content


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
