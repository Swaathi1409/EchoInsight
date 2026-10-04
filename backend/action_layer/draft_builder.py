"""
backend/action_layer/draft_builder.py
Tier 1 deterministic follow-up draft generator.

Rules:
- Uses verified facts only (from stored analysis + commitments).
- [CUSTOMER] and [AGENT] placeholders — no names.
- Unknown facts use explicit placeholders like [supervisor to confirm time].
- Draft must pass the existing prohibited-promise matcher before storage.
- Banner: "Draft for review. Not sent automatically."
- No outbound sending integration.
"""
from __future__ import annotations

from typing import Any

# Reuse the existing prohibited-phrase matcher
try:
    from backend.qa.phrase_matcher import PhraseMatcher
    _has_phrase_matcher = True
except ImportError:
    _has_phrase_matcher = False

DRAFT_BANNER = "Draft for review. Not sent automatically."
DRAFT_LABEL = "Tier 1 deterministic template — human review required before use"


def build_template_draft(
    *,
    analysis: dict[str, Any],
    open_commitments: list[dict[str, Any]],
    intervention_type: str,
    conversation_id: str,
) -> dict[str, Any]:
    """
    Build a deterministic follow-up draft from verified stored facts only.

    Returns:
        {content, facts_used, placeholders, gate_status, banner}
    """
    resolution = analysis.get("resolution", "unresolved")
    reasons: list[str] = analysis.get("reasons", [])
    summary: str = analysis.get("summary", "")
    false_resolution: bool = analysis.get("false_resolution", False)

    facts_used: list[str] = []
    placeholders: list[str] = []

    # ── Header ────────────────────────────────────────────────────────────────
    lines = [
        f"[{DRAFT_BANNER}]",
        "",
        "Dear [CUSTOMER],",
        "",
    ]

    # ── Issue summary ─────────────────────────────────────────────────────────
    if reasons:
        reason_text = ", ".join(reasons[:3])  # cap at 3
        lines.append(
            f"We are following up regarding your recent contact about: {reason_text}."
        )
        facts_used.append(f"call_reasons: {reason_text}")
    else:
        lines.append("We are following up regarding your recent contact.")
        placeholders.append("[reason not recorded]")

    lines.append("")

    # ── Resolution status ─────────────────────────────────────────────────────
    if resolution == "resolved" and not false_resolution:
        lines.append(
            "We understand the matter was addressed during your call. "
            "If there is anything further we can help with, please do not hesitate to contact us."
        )
        facts_used.append(f"resolution: {resolution}")
    elif false_resolution:
        lines.append(
            "We note that the call was marked resolved, but our records indicate the issue "
            "may require further attention. We will follow up to ensure it is fully addressed."
        )
        facts_used.append("false_resolution: True")
    elif resolution in ("unresolved", "partially_resolved", "pending"):
        lines.append(
            "We understand that the matter was not fully resolved during your call. "
            "We are working to address it and will follow up as soon as possible."
        )
        facts_used.append(f"resolution: {resolution}")
    elif resolution == "escalated":
        lines.append(
            "Your concern has been escalated to [supervisor to confirm escalation team]. "
            "We will be in touch with an update."
        )
        facts_used.append(f"resolution: {resolution}")
        placeholders.append("[supervisor to confirm escalation team]")
    else:
        lines.append(
            "We are reviewing your case and will follow up with an update."
        )
        placeholders.append("[supervisor to confirm update timeline]")

    lines.append("")

    # ── Open commitments ──────────────────────────────────────────────────────
    if open_commitments:
        lines.append("Outstanding commitments from your call:")
        for c in open_commitments:
            desc = c.get("description", "[commitment description not available]")
            deadline = c.get("deadline") or "[supervisor to confirm deadline]"
            if not c.get("deadline"):
                placeholders.append(f"[supervisor to confirm deadline for: {desc[:40]}]")
            lines.append(f"  - {desc} (by: {deadline})")
            facts_used.append(f"commitment: {desc[:60]}")
        lines.append("")

    # ── Intervention-specific note ─────────────────────────────────────────────
    if intervention_type == "firm_exit_intent":
        lines.append(
            "We respect your decision and will process your request as discussed. "
            "Should you wish to reconnect with us in the future, we would be happy to help."
        )
    elif intervention_type == "relationship_repair":
        lines.append(
            "We sincerely apologise for the inconvenience experienced. "
            "We are committed to resolving this matter to your satisfaction."
        )
    elif intervention_type == "price_sensitive":
        lines.append(
            "If you have any questions about your plan or billing, "
            "please contact us and we will be happy to review the options available to you."
        )

    lines.append("")
    lines.append("Kind regards,")
    lines.append("[AGENT]")
    lines.append("[supervisor to confirm signatory before sending]")
    placeholders.append("[supervisor to confirm signatory before sending]")

    content = "\n".join(lines)

    # ── Gate: prohibited-phrase check ─────────────────────────────────────────
    gate_status = "passed"
    if _has_phrase_matcher:
        try:
            matcher = PhraseMatcher()
            violations = matcher.check(content)
            if violations:
                gate_status = "prohibited_phrase_detected"
        except Exception:
            gate_status = "check_unavailable"
    else:
        gate_status = "check_unavailable"

    return {
        "content": content,
        "facts_used": facts_used,
        "placeholders": placeholders,
        "gate_status": gate_status,
        "banner": DRAFT_BANNER,
        "label": DRAFT_LABEL,
        "kind": "template",
    }
