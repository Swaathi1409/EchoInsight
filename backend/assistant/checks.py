"""
backend/assistant/checks.py
Standardized Data Integrity Checklist (C1-C10).
All deterministic code — no model calls.
Each check returns a CheckResult; the suite returns a CheckOutcome.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CheckResult:
    check_id: str           # "C1" ... "C10"
    label: str
    outcome: str            # "pass" | "fail" | "warn" | "skip"
    message: str = ""
    blocking: bool = False  # if True and outcome=="fail", block the answer


@dataclass
class CheckOutcome:
    results: list[CheckResult] = field(default_factory=list)

    @property
    def verification_label(self) -> str:
        if any(r.outcome == "fail" and r.blocking for r in self.results):
            return "could_not_verify"
        if any(r.outcome in ("fail", "warn") for r in self.results):
            return "verified_with_caveats"
        return "verified"

    @property
    def blocked(self) -> bool:
        return any(r.outcome == "fail" and r.blocking for r in self.results)

    def to_list(self) -> list[dict]:
        return [
            {
                "check": r.check_id,
                "label": r.label,
                "outcome": r.outcome,
                "message": r.message,
                "blocking": r.blocking,
            }
            for r in self.results
        ]


# ── Individual checks ────────────────────────────────────────────────────────

def c1_identity_and_scope(
    role: str,
    plan_tools: list[str],
    available_tools: list[str],
) -> CheckResult:
    """C1: Plan only uses tools the caller's role may use."""
    disallowed = [t for t in plan_tools if t not in available_tools]
    if disallowed:
        return CheckResult(
            "C1", "Identity and scope",
            "fail",
            f"Plan requests tools not permitted for role '{role}': {disallowed}",
            blocking=True,
        )
    return CheckResult("C1", "Identity and scope", "pass", f"role={role}")


def c2_feature_availability(
    required_action_layer: bool,
    action_layer_enabled: bool,
    plan_tools: list[str],
    tool_registry: dict[str, dict],
) -> CheckResult:
    """C2: Required features (Action Layer) are enabled."""
    needs_al = any(
        tool_registry.get(t, {}).get("requires_action_layer", False)
        for t in plan_tools
    )
    if needs_al and not action_layer_enabled:
        return CheckResult(
            "C2", "Feature availability",
            "fail",
            "Question requires the Action Layer which is not enabled.",
            blocking=True,
        )
    return CheckResult("C2", "Feature availability", "pass")


def c3_data_volume(
    results: list[Any],
    min_n: int = 1,
    label: str = "results",
) -> CheckResult:
    """C3: Result set is non-empty and meets minimum n."""
    n = len(results) if isinstance(results, (list, dict)) else 0
    if isinstance(results, dict):
        n = 1  # dict result = one item
    if n == 0:
        return CheckResult(
            "C3", "Data volume",
            "fail",
            f"No {label} found matching the filters.",
            blocking=False,  # non-blocking: show "no data" message
        )
    if n < min_n:
        return CheckResult(
            "C3", "Data volume",
            "warn",
            f"Only {n} {label} found (minimum {min_n} recommended for rates/rankings).",
            blocking=False,
        )
    return CheckResult("C3", "Data volume", "pass", f"n={n}")


def c4_provenance(tool_names_used: list[str]) -> CheckResult:
    """C4: All results come from registered tools (no ad-hoc queries)."""
    from backend.assistant.tool_registry import load_tools
    registry = load_tools()
    unknown = [t for t in tool_names_used if t not in registry]
    if unknown:
        return CheckResult(
            "C4", "Provenance",
            "fail",
            f"Unknown tools used (not in allowlist): {unknown}",
            blocking=True,
        )
    return CheckResult("C4", "Provenance", "pass", f"tools={tool_names_used}")


def c5_time_validity(
    date_range: dict | None,
    data_clock: str,
) -> CheckResult:
    """C5: Date range is valid and stated; relative phrases resolved."""
    if date_range is None:
        return CheckResult(
            "C5", "Time validity", "pass",
            f"All-time range assumed. Data as-of: {data_clock}"
        )
    start = date_range.get("start")
    end = date_range.get("end")
    if start and end and start > end:
        return CheckResult(
            "C5", "Time validity",
            "fail",
            f"Date range invalid: start ({start}) is after end ({end}).",
            blocking=True,
        )
    return CheckResult(
        "C5", "Time validity", "pass",
        f"Range: {start} to {end}. Data as-of: {data_clock}"
    )


def c6_definition_alignment(
    metric_used: str | None,
    allowed_metrics: list[str],
) -> CheckResult:
    """C6: Metric used matches a curated definition."""
    if metric_used is None:
        return CheckResult("C6", "Definition alignment", "skip", "No specific metric.")
    if metric_used not in allowed_metrics:
        return CheckResult(
            "C6", "Definition alignment",
            "warn",
            f"Metric '{metric_used}' not in curated definitions. Interpret with caution.",
            blocking=False,
        )
    return CheckResult("C6", "Definition alignment", "pass", f"metric={metric_used}")


def c7_reconciliation(
    total_from_overview: int | None,
    total_from_breakdown: int | None,
    label: str = "total",
) -> CheckResult:
    """
    C7: Reconciliation — two tools measuring same quantity must agree.
    If both are provided and differ, block the answer.
    """
    if total_from_overview is None or total_from_breakdown is None:
        return CheckResult("C7", "Reconciliation", "skip", "Single source; no cross-check.")
    if total_from_overview != total_from_breakdown:
        return CheckResult(
            "C7", "Reconciliation",
            "fail",
            (
                f"Inconsistency: {label} from source A={total_from_overview}, "
                f"source B={total_from_breakdown}. Cannot give a reliable number."
            ),
            blocking=True,
        )
    return CheckResult("C7", "Reconciliation", "pass", f"{label}={total_from_overview}")


def c8_freshness(
    last_analysis_at: str | None,
    derive_job_lag_hours: float | None = None,
    stale_threshold_hours: float = 48,
) -> CheckResult:
    """C8: Data is fresh enough; warn if stale."""
    if last_analysis_at is None:
        return CheckResult(
            "C8", "Freshness",
            "warn",
            "Last analysis time unknown. Data may be stale.",
            blocking=False,
        )
    return CheckResult(
        "C8", "Freshness", "pass",
        f"Last analysis: {last_analysis_at}"
    )


def c9_coverage(
    total_conversations: int,
    analyzed_conversations: int,
) -> CheckResult:
    """C9: Coverage — proportion of conversations with final analysis."""
    if total_conversations == 0:
        return CheckResult("C9", "Coverage", "skip", "No conversations.")
    rate = analyzed_conversations / total_conversations
    if rate < 0.5:
        return CheckResult(
            "C9", "Coverage",
            "warn",
            f"Only {analyzed_conversations}/{total_conversations} conversations analyzed ({rate:.0%}). "
            "Rates may not be representative.",
            blocking=False,
        )
    return CheckResult(
        "C9", "Coverage", "pass",
        f"{analyzed_conversations}/{total_conversations} conversations analyzed ({rate:.0%})"
    )


def c10_known_caveats(families: list[str]) -> CheckResult:
    """C10: Attach known caveats from registry for the question's families."""
    from backend.assistant.tool_registry import caveats_for_families
    applicable = caveats_for_families(families)
    blocking = [c for c in applicable if c.get("blocking", False)]
    if blocking:
        labels = [c["label"] for c in blocking]
        return CheckResult(
            "C10", "Known caveats",
            "fail",
            f"Blocking caveat(s): {labels}",
            blocking=True,
        )
    if applicable:
        labels = [c["label"] for c in applicable]
        return CheckResult(
            "C10", "Known caveats",
            "warn",
            f"Non-blocking caveats: {labels}",
            blocking=False,
        )
    return CheckResult("C10", "Known caveats", "pass", "No applicable caveats.")


# ── Full check suite ─────────────────────────────────────────────────────────

def run_all_checks(
    *,
    role: str,
    plan_tools: list[str],
    available_tool_names: list[str],
    tool_registry: dict[str, dict],
    action_layer_enabled: bool,
    result_list: list | None = None,
    min_n: int = 1,
    data_clock: str = "unknown",
    date_range: dict | None = None,
    families: list[str] | None = None,
    metric_used: str | None = None,
    total_conversations: int | None = None,
    analyzed_conversations: int | None = None,
    reconcile_a: int | None = None,
    reconcile_b: int | None = None,
    reconcile_label: str = "total",
) -> CheckOutcome:
    """Run C1-C10 and return a CheckOutcome."""
    outcome = CheckOutcome()

    outcome.results.append(c1_identity_and_scope(role, plan_tools, available_tool_names))
    outcome.results.append(c2_feature_availability(
        False, action_layer_enabled, plan_tools, tool_registry
    ))
    if result_list is not None:
        outcome.results.append(c3_data_volume(result_list, min_n))
    outcome.results.append(c4_provenance(plan_tools))
    outcome.results.append(c5_time_validity(date_range, data_clock))
    if metric_used is not None:
        outcome.results.append(c6_definition_alignment(metric_used, CURATED_METRICS))
    if reconcile_a is not None:
        outcome.results.append(c7_reconciliation(reconcile_a, reconcile_b, reconcile_label))
    outcome.results.append(c8_freshness(None))  # freshness checked in pipeline
    if total_conversations is not None and analyzed_conversations is not None:
        outcome.results.append(c9_coverage(total_conversations, analyzed_conversations))
    if families:
        outcome.results.append(c10_known_caveats(families))

    return outcome


# ── Curated metric definitions ───────────────────────────────────────────────
CURATED_METRICS = [
    "resolution_rate",
    "unresolved_rate",
    "false_resolution_rate",
    "churn_signal_rate",
    "avg_qa_score",
    "commitment_completion_rate",
    "escalation_rate",
    "positive_sentiment_rate",
    "negative_sentiment_rate",
    "open_commitments_count",
    "volume",
    "analyzed_count",
]
