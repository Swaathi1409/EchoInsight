"""
Groq LLM client with token budget enforcement and retry.
"""
from __future__ import annotations
import logging
from typing import Any
import groq
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from backend.config.settings import get_settings

logger = logging.getLogger(__name__)
_client: groq.AsyncGroq | None = None


def get_client() -> groq.AsyncGroq:
    global _client
    if _client is None:
        _client = groq.AsyncGroq(api_key=get_settings().groq_api_key)
    return _client


@retry(
    retry=retry_if_exception_type((groq.RateLimitError, groq.APIConnectionError)),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    stop=stop_after_attempt(3),
    reraise=True,
)
async def chat_json(
    messages: list[dict[str, str]],
    schema: dict[str, Any],
    model: str | None = None,
    temperature: float = 0.0,
) -> tuple[dict[str, Any], int, int]:
    """
    Call Groq with json_schema response format.
    Returns (parsed_dict, prompt_tokens, completion_tokens).

    Raises BudgetExceededError if the daily token budget is exhausted.
    """
    import json
    from backend.llm.budget import check_budget, check_and_record, BudgetExceededError

    s = get_settings()
    m = model or s.llm_primary_model
    client = get_client()

    # Pre-flight budget check
    try:
        check_budget(s.llm_daily_token_budget)
    except BudgetExceededError as exc:
        logger.error("Token budget exhausted before LLM call: %s", exc)
        raise

    resp = await client.chat.completions.create(
        model=m,
        messages=messages,  # type: ignore[arg-type]
        temperature=temperature,
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "response", "schema": schema, "strict": True},
        },
    )
    usage = resp.usage
    prompt_tokens = usage.prompt_tokens if usage else 0
    completion_tokens = usage.completion_tokens if usage else 0
    content = resp.choices[0].message.content or "{}"

    # Record after successful call (soft enforcement — warn if budget exceeded)
    try:
        check_and_record(prompt_tokens, completion_tokens, s.llm_daily_token_budget)
    except BudgetExceededError:
        logger.warning(
            "Token budget exceeded after call. Model=%s prompt=%d completion=%d",
            m, prompt_tokens, completion_tokens
        )

    return json.loads(content), prompt_tokens, completion_tokens
