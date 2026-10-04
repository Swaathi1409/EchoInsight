"""
backend/assistant/tool_executor.py
Executes registered tools using the caller's auth token (scope parity with UI).
Each call: validates params, hits the same API route the browser uses, applies
timeout and result size limits. Never touches the DB directly.

IMPORTANT: execute_tool is async — uses httpx so the uvicorn event loop is
NOT blocked during self-calls. Synchronous urllib would deadlock because the
same process handles both the caller and the tool endpoint.
"""
from __future__ import annotations

import hashlib
import json
import time
import urllib.parse
from typing import Any

import httpx

from backend.assistant.tool_registry import get_tool

# Internal base URL for self-calls — loopback only
_INTERNAL_BASE = "http://127.0.0.1:8000"
_TIMEOUT_SECONDS = 12
_MAX_RESULT_BYTES = 200_000  # 200 KB cap on tool results


class ToolCallError(Exception):
    def __init__(self, tool_name: str, status: int, message: str):
        self.tool_name = tool_name
        self.status = status
        self.message = message
        super().__init__(f"Tool {tool_name} failed ({status}): {message}")


def _param_hash(params: dict) -> str:
    """Stable hash of params for logging — never logs values."""
    encoded = json.dumps(params, sort_keys=True, default=str).encode()
    return hashlib.sha256(encoded).hexdigest()[:12]


async def execute_tool(
    *,
    tool_name: str,
    params: dict[str, Any],
    caller_token: str,
) -> tuple[dict | list, dict]:
    """
    Execute a tool and return (result, log_entry). ASYNC.

    result: parsed JSON from the endpoint (trimmed to _MAX_RESULT_BYTES)
    log_entry: {tool_name, param_hash, status, latency_ms} — NO param values, NO result body
    """
    tool = get_tool(tool_name)  # raises KeyError if not in allowlist
    method = tool.get("method", "GET").upper()
    path_template = tool["path_template"]

    # Build URL: substitute path params, add query params
    path_params = {k: v for k, v in params.items() if f"{{{k}}}" in path_template}
    query_params = {k: v for k, v in params.items() if k not in path_params}

    path = path_template
    for k, v in path_params.items():
        path = path.replace(f"{{{k}}}", urllib.parse.quote(str(v)))

    if query_params:
        path = path + "?" + urllib.parse.urlencode(
            {k: v for k, v in query_params.items() if v is not None}
        )

    url = _INTERNAL_BASE + path
    headers = {
        "Authorization": f"Bearer {caller_token}",
        "Content-Type": "application/json",
    }

    t0 = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            resp = await client.request(method, url, headers=headers)
    except httpx.TimeoutException as e:
        latency_ms = (time.perf_counter() - t0) * 1000
        raise ToolCallError(tool_name, 0, f"timed out after {_TIMEOUT_SECONDS}s") from e
    except Exception as e:
        latency_ms = (time.perf_counter() - t0) * 1000
        raise ToolCallError(tool_name, 0, str(e)) from e

    latency_ms = (time.perf_counter() - t0) * 1000
    status = resp.status_code

    if status >= 400:
        raise ToolCallError(tool_name, status, resp.text[:200])

    raw = resp.content[:_MAX_RESULT_BYTES]
    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        result = {"raw": raw.decode(errors="replace")[:2000]}

    log_entry = {
        "tool_name": tool_name,
        "param_hash": _param_hash(params),
        "status": status,
        "latency_ms": round(latency_ms, 1),
        "error": False,
    }
    return result, log_entry
