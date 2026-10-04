"""
backend/assistant/tool_registry.py
Loads tools.yaml, validates all entries, and provides scoped tool lookups.
Test: every registered tool uses method=GET; no write route allowed.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

_TOOLS_YAML = Path(__file__).parent / "tools.yaml"
_CAVEATS_YAML = Path(__file__).parent / "known_caveats.yaml"

WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


@lru_cache(maxsize=1)
def load_tools() -> dict[str, dict[str, Any]]:
    """Load and validate tool registry. Raises ValueError on any write-capable tool."""
    raw = yaml.safe_load(_TOOLS_YAML.read_text(encoding="utf-8"))
    registry: dict[str, dict[str, Any]] = {}
    for tool in raw["tools"]:
        name = tool["name"]
        method = tool.get("method", "GET").upper()
        if method in WRITE_METHODS:
            raise ValueError(
                f"SECURITY: tool '{name}' uses method={method} — only GET is allowed. "
                "Remove it from tools.yaml."
            )
        registry[name] = tool
    return registry


@lru_cache(maxsize=1)
def load_caveats() -> dict[str, dict[str, Any]]:
    raw = yaml.safe_load(_CAVEATS_YAML.read_text(encoding="utf-8"))
    return raw["caveats"]


def get_tool(name: str) -> dict[str, Any]:
    tools = load_tools()
    if name not in tools:
        raise KeyError(f"Unknown tool: '{name}'. Not in allowlist.")
    return tools[name]


def tools_for_role(role: str, action_layer_enabled: bool) -> list[dict[str, Any]]:
    """Return tools the caller's role may use given feature availability."""
    all_tools = load_tools()
    result = []
    for tool in all_tools.values():
        req_role = tool.get("required_role", "any")
        if req_role == "admin" and role != "admin":
            continue
        if req_role == "supervisor_or_admin" and role not in ("admin", "supervisor"):
            continue
        if tool.get("requires_action_layer", False) and not action_layer_enabled:
            continue
        result.append(tool)
    return result


def compact_catalog(role: str, action_layer_enabled: bool) -> list[dict[str, Any]]:
    """Compact catalog for the planner prompt — name, description, params, families."""
    tools = tools_for_role(role, action_layer_enabled)
    return [
        {
            "name": t["name"],
            "label": t["label"],
            "description": t["description"].strip(),
            "params": t.get("params", {}),
            "families": t.get("families", []),
            "enabled": True,
        }
        for t in tools
    ]


def caveats_for_families(families: list[str]) -> list[dict[str, Any]]:
    """Return caveats that apply to any of the given families."""
    caveats = load_caveats()
    result = []
    for key, cav in caveats.items():
        if any(f in cav.get("families", []) for f in families):
            result.append({"key": key, **cav})
    return result
