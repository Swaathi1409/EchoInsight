"""
backend/assistant/tool_executor.py
Executes registered tools using the caller's auth token (scope parity with UI).
Each call: validates params, hits the same API route the browser uses, applies
timeout and result size limits. Never touches the DB directly.
"""
from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from backend.assistant.tool_registry import get_tool

# Internal base URL for self-calls — same process, loopback only
_INTERNAL_BASE = "http://127.0.0.1:8000"
_TIMEOUT_SECONDS = 10
_MAX_RESULT_BYTES = 200_000  # 200 KB cap on tool results sent upstream


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


def execute_tool(
    *,
    tool_name: str,
    params: dict[str, Any],
    caller_token: str,
) -> tuple[dict | list, dict]:
    """
    Execute a tool and return (result, log_entry).

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
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {caller_token}",
            "Content-Type": "application/json",
        },
        method=method,
    )

    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT_SECONDS) as resp:
            raw = resp.read(_MAX_RESULT_BYTES)
            status = resp.status
    except urllib.error.HTTPError as e:
        latency_ms = (time.perf_counter() - t0) * 1000
        body = e.read(500).decode(errors="replace")
        log_entry = {
            "tool_name": tool_name,
            "param_hash": _param_hash(params),
            "status": e.code,
            "latency_ms": round(latency_ms, 1),
            "error": True,
        }
        raise ToolCallError(tool_name, e.code, body) from e
    except Exception as e:
        latency_ms = (time.perf_counter() - t0) * 1000
        log_entry = {
            "tool_name": tool_name,
            "param_hash": _param_hash(params),
            "status": 0,
            "latency_ms": round(latency_ms, 1),
            "error": True,
        }
        raise ToolCallError(tool_name, 0, str(e)) from e

    latency_ms = (time.perf_counter() - t0) * 1000
    result = json.loads(raw)

    log_entry = {
        "tool_name": tool_name,
        "param_hash": _param_hash(params),
        "status": status,
        "latency_ms": round(latency_ms, 1),
        "error": False,
    }
    return result, log_entry
