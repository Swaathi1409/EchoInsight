"""
Groq LLM client with token budget enforcement and retry.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from openai import AsyncOpenAI

from backend.config.settings import get_settings

logger = logging.getLogger(__name__)
_client: AsyncOpenAI | None = None


def get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        s = get_settings()
        if s.openrouter_api_key:
            _client = AsyncOpenAI(
                api_key=s.openrouter_api_key,
                base_url="https://openrouter.ai/api/v1",
            )
        else:
            # Fallback to groq using OpenAI compatible endpoint
            _client = AsyncOpenAI(
                api_key=s.groq_api_key,
                base_url="https://api.groq.com/openai/v1",
            )
    return _client


# Simple retry logic without tenacity to avoid dependency issues if needed, or keep tenacity.
# We'll just write a simple retry loop since OpenAI exceptions differ from Groq exceptions.
async def chat_json(
    messages: list[dict[str, str]],
    schema: dict[str, Any],
    model: str | None = None,
    temperature: float = 0.0,
) -> tuple[dict[str, Any], int, int]:
    """
    Call LLM with JSON format.
    Returns (parsed_dict, prompt_tokens, completion_tokens).
    """
    from backend.llm.budget import BudgetExceededError, check_and_record, check_budget

    s = get_settings()
    m = model
    if not m:
        m = s.openrouter_model if s.openrouter_api_key else s.llm_primary_model

    client = get_client()

    try:
        check_budget(s.llm_daily_token_budget)
    except BudgetExceededError as exc:
        logger.error("Token budget exhausted before LLM call: %s", exc)
        raise

    # Append schema to prompt so models not supporting strict schema still output JSON
    schema_str = json.dumps(schema)
    modified_messages = list(messages)
    modified_messages.append({
        "role": "user",
        "content": f"Please provide the output in valid JSON matching this schema:\n{schema_str}"
    })

    last_exc = None
    for attempt in range(3):
        try:
            resp = await client.chat.completions.create(
                model=m,
                messages=modified_messages,  # type: ignore
                temperature=temperature,
                response_format={"type": "json_object"},
                max_tokens=2000,
            )
            usage = resp.usage
            prompt_tokens = usage.prompt_tokens if usage else 0
            completion_tokens = usage.completion_tokens if usage else 0
            content = resp.choices[0].message.content or "{}"

            try:
                check_and_record(prompt_tokens, completion_tokens, s.llm_daily_token_budget)
            except BudgetExceededError:
                logger.warning("Token budget exceeded after call.")

            import re

            # Find the outermost JSON object or array
            match = re.search(r'(\{[\s\S]*\}|\[[\s\S]*\])', content)
            if match:
                content = match.group(1)
            else:
                # Fallback to stripping markdown if braces aren't found for some reason
                match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content)
                if match:
                    content = match.group(1)

            content = content.strip()
            if not content:
                content = "{}"

            return json.loads(content), prompt_tokens, completion_tokens
        except Exception as e:
            last_exc = e
            logger.warning(f"LLM call failed (attempt {attempt+1}/3): {e}")
            import asyncio
            await asyncio.sleep(2 ** attempt)

    raise last_exc or Exception("LLM call failed after 3 attempts")
