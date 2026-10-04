"""
backend/assistant/calc_tools.py
Deterministic helper computations — executed by code, never by the model.
Results are referenced via {{calc:call_id}} placeholders in composed answers.
"""
from __future__ import annotations

import uuid
from typing import Any


def _cid() -> str:
    return f"calc_{uuid.uuid4().hex[:8]}"


def percent(numerator: int | float, denominator: int | float) -> dict:
    """Returns percentage value and a formatted string."""
    if not denominator:
        return {"call_id": _cid(), "value": None, "formatted": "N/A (no data)"}
    val = numerator / denominator * 100
    cid = _cid()
    return {"call_id": cid, "value": round(val, 1), "formatted": f"{val:.1f}%"}


def difference(a: int | float, b: int | float, label_a: str = "A", label_b: str = "B") -> dict:
    cid = _cid()
    diff = a - b
    return {
        "call_id": cid,
        "value": round(diff, 3),
        "formatted": f"{diff:+.1f}",
        "label": f"{label_a} minus {label_b}",
    }


def ratio(numerator: int | float, denominator: int | float, decimals: int = 3) -> dict:
    cid = _cid()
    if not denominator:
        return {"call_id": cid, "value": None, "formatted": "N/A"}
    val = round(numerator / denominator, decimals)
    return {"call_id": cid, "value": val, "formatted": str(val)}


def top_n(items: list[dict], key: str, n: int = 5, ascending: bool = False) -> dict:
    """Return top-N items sorted by key."""
    cid = _cid()
    sorted_items = sorted(items, key=lambda x: x.get(key, 0), reverse=not ascending)
    return {"call_id": cid, "value": sorted_items[:n], "key": key, "n": n}


def rank(items: list[dict], key: str, target_id: str, id_key: str = "id") -> dict:
    """Return rank (1-indexed) of target_id among items sorted by key descending."""
    cid = _cid()
    sorted_items = sorted(items, key=lambda x: x.get(key, 0), reverse=True)
    for i, item in enumerate(sorted_items, 1):
        if str(item.get(id_key, "")) == str(target_id):
            return {"call_id": cid, "value": i, "formatted": f"#{i} of {len(sorted_items)}"}
    return {"call_id": cid, "value": None, "formatted": "not found"}


def sum_field(items: list[dict], key: str) -> dict:
    cid = _cid()
    total = sum(item.get(key, 0) or 0 for item in items)
    return {"call_id": cid, "value": total, "formatted": f"{total:,}"}


def count_where(items: list[dict], key: str, value: Any) -> dict:
    cid = _cid()
    n = sum(1 for item in items if item.get(key) == value)
    return {"call_id": cid, "value": n, "formatted": str(n)}
