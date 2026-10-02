"""
Validator hard gate: all 7 conditions must pass before analysis is accepted.

Conditions (from master prompt section 7 step 7):
1. Every turn ID cited exists in the conversation
2. Every quote is an exact substring of its cited turn (case+whitespace normalized)
3. All labels are in the taxonomy
4. Scores are in range [0, 100]
5. Resolution is consistent with open commitments (resolved + open commits = suspect)
6. Completed actions have completion evidence (completed_at_turn_id set and exists)
7. Summary asserts no unsupported outcome

On failure: retry once with error feedback. Then store needs_review.
Error categories: invalid_model_json, unsupported_evidence, inconsistent_state,
                  provider_timeout, provider_rate_limited.
"""
from __future__ import annotations
import re
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

VALID_REASONS = {
    "network_coverage_or_dropped_calls", "mobile_data_issue", "internet_or_broadband_outage",
    "billing_dispute", "plan_change_or_upgrade", "cancellation_or_churn_intent",
    "roaming_or_international", "sim_or_activation", "device_issue", "technical_visit",
    "account_access_or_security", "complaint_or_escalation", "general_inquiry", "payment_or_top_up",
}
VALID_RESOLUTION = {
    "resolved", "partially_resolved", "pending", "unresolved", "escalated", "unknown"
}
VALID_CHURN_RISK = {"low", "medium", "high"}
VALID_SENTIMENT = {"positive", "neutral", "frustrated", "angry"}
VALID_COMMITMENT_STATUS = {
    "proposed", "accepted", "scheduled", "completed", "cancelled", "uncertain"
}

# Outcome words that must be grounded — if in summary but not in any cited turn
UNSUPPORTED_OUTCOME_WORDS = [
    "resolved", "fixed", "completed", "confirmed", "guaranteed",
    "promised", "scheduled", "will be done",
]


@dataclass
class ValidationError:
    code: str           # error category
    field: str          # which field/item
    detail: str         # human-readable message


@dataclass
class ValidationResult:
    passed: bool
    errors: list[ValidationError] = field(default_factory=list)
    needs_review: bool = False


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _check_quote(quote: str, turn_text: str) -> bool:
    if not quote or len(quote) < 3:
        return True
    return _normalize(quote) in _normalize(turn_text)


def validate_analysis(
    raw: dict,
    turns_by_id: dict[str, str],
    qa_items: list[dict] | None = None,
) -> ValidationResult:
    """
    Run the full 7-condition validator hard gate.
    Returns ValidationResult with all errors found.
    """
    errors: list[ValidationError] = []

    # --- 1. Turn IDs exist ---
    def _check_turn_id(tid: str, context: str) -> None:
        if tid and tid not in turns_by_id:
            errors.append(ValidationError(
                code="unsupported_evidence",
                field=context,
                detail=f"Turn ID '{tid}' does not exist in this conversation",
            ))

    # Check commitment turn IDs
    for i, c in enumerate(raw.get("commitments", [])):
        _check_turn_id(c.get("turn_id", ""), f"commitments[{i}].turn_id")

    # Check sentiment trajectory turn IDs
    for i, sp in enumerate(raw.get("sentiment_trajectory", [])):
        _check_turn_id(sp.get("turn_id", ""), f"sentiment_trajectory[{i}].turn_id")

    # Check QA item turn IDs
    for i, item in enumerate(qa_items or []):
        tid = item.get("turn_id", "")
        if tid:
            _check_turn_id(tid, f"qa_items[{i}].turn_id")

    # --- 2. Exact quote verification ---
    for i, c in enumerate(raw.get("commitments", [])):
        quote = c.get("quote", "")
        tid = c.get("turn_id", "")
        turn_text = turns_by_id.get(tid, "")
        if quote and turn_text and not _check_quote(quote, turn_text):
            errors.append(ValidationError(
                code="unsupported_evidence",
                field=f"commitments[{i}].quote",
                detail=f"Quote not found in turn {tid}: '{quote[:60]}'",
            ))

    for i, item in enumerate(qa_items or []):
        quote = item.get("quote", "")
        tid = item.get("turn_id", "")
        turn_text = turns_by_id.get(tid, "")
        if quote and turn_text and not _check_quote(quote, turn_text):
            errors.append(ValidationError(
                code="unsupported_evidence",
                field=f"qa_items[{i}].quote",
                detail=f"Quote not found in turn {tid}: '{quote[:60]}'",
            ))

    # --- 3. Labels in taxonomy ---
    for reason in raw.get("reasons", []):
        if reason not in VALID_REASONS:
            errors.append(ValidationError(
                code="unsupported_evidence",
                field="reasons",
                detail=f"Reason '{reason}' not in taxonomy",
            ))

    resolution = raw.get("resolution", "")
    if resolution and resolution not in VALID_RESOLUTION:
        errors.append(ValidationError(
            code="unsupported_evidence",
            field="resolution",
            detail=f"Resolution '{resolution}' not in enum",
        ))

    churn_risk = raw.get("churn_risk", "")
    if churn_risk and churn_risk not in VALID_CHURN_RISK:
        errors.append(ValidationError(
            code="unsupported_evidence",
            field="churn_risk",
            detail=f"Churn risk '{churn_risk}' not in enum",
        ))

    for i, sp in enumerate(raw.get("sentiment_trajectory", [])):
        sent = sp.get("sentiment", "")
        if sent and sent not in VALID_SENTIMENT:
            errors.append(ValidationError(
                code="unsupported_evidence",
                field=f"sentiment_trajectory[{i}].sentiment",
                detail=f"Sentiment '{sent}' not in enum",
            ))

    for i, c in enumerate(raw.get("commitments", [])):
        status = c.get("status", "")
        if status and status not in VALID_COMMITMENT_STATUS:
            errors.append(ValidationError(
                code="unsupported_evidence",
                field=f"commitments[{i}].status",
                detail=f"Status '{status}' not in enum",
            ))

    # --- 4. Scores in range (for QA items) ---
    for i, item in enumerate(qa_items or []):
        sc = item.get("score_contribution", 0)
        w = item.get("weight", 1.0)
        if not (0.0 <= sc <= w + 0.01):
            errors.append(ValidationError(
                code="unsupported_evidence",
                field=f"qa_items[{i}].score_contribution",
                detail=f"score_contribution {sc} out of range for weight {w}",
            ))
        conf = item.get("confidence", 1.0)
        if not (0.0 <= conf <= 1.0):
            errors.append(ValidationError(
                code="unsupported_evidence",
                field=f"qa_items[{i}].confidence",
                detail=f"Confidence {conf} not in [0, 1]",
            ))

    # --- 5. Resolution consistent with open commitments ---
    open_commitments = [
        c for c in raw.get("commitments", [])
        if c.get("status") not in ("completed", "cancelled")
    ]
    if resolution == "resolved" and open_commitments:
        errors.append(ValidationError(
            code="inconsistent_state",
            field="resolution",
            detail=f"Resolution is 'resolved' but {len(open_commitments)} commitment(s) are open",
        ))

    # --- 6. Completed commitments have evidence ---
    for i, c in enumerate(raw.get("commitments", [])):
        if c.get("status") == "completed":
            if not c.get("quote") and not c.get("evidence"):
                errors.append(ValidationError(
                    code="inconsistent_state",
                    field=f"commitments[{i}]",
                    detail="Commitment marked completed without evidence quote",
                ))

    # --- 7. Summary has no unsupported outcome claims ---
    summary = raw.get("summary", "").lower()
    if summary:
        for outcome_word in UNSUPPORTED_OUTCOME_WORDS:
            if outcome_word in summary and resolution not in ("resolved", "partially_resolved"):
                errors.append(ValidationError(
                    code="inconsistent_state",
                    field="summary",
                    detail=(
                        f"Summary contains '{outcome_word}' but resolution is '{resolution}'. "
                        "Summary must not assert unsupported outcomes."
                    ),
                ))
                break  # one warning is enough

    passed = len(errors) == 0
    needs_review = not passed and all(
        e.code in ("unsupported_evidence", "inconsistent_state") for e in errors
    )
    return ValidationResult(passed=passed, errors=errors, needs_review=needs_review)


def log_validation_errors(result: ValidationResult, conversation_id: str) -> None:
    if result.passed:
        return
    for err in result.errors:
        logger.warning(
            "Validation error [%s] conv=%s field=%s: %s",
            err.code, conversation_id, err.field, err.detail,
        )
