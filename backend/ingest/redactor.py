"""
PII redaction for transcript turns.

Replaces sensitive patterns before any storage, logging, or LLM call.
All replacements use bracketed tags: [PHONE], [ACCOUNT], [PIN], etc.
Regex-first; no ML model dependency.
"""
from __future__ import annotations

import re

# Ordered list of (pattern, tag) — order matters for overlapping matches
_RULES: list[tuple[re.Pattern[str], str]] = [
    # Card numbers (before account numbers)
    (re.compile(r"\b(?:\d[ -]?){13,16}\b"), "[CARD]"),
    # Account numbers (6-12 digits following context keywords) - BEFORE phone
    (re.compile(r"(?i)(?:account|acct|account\s*number|acct\s*#)[:\s#]*(\d{6,12})"), "[ACCOUNT]"),
    # Standalone 8-12 digit numbers (account IDs) - BEFORE phone
    (re.compile(r"(?<!\d)\d{8,12}(?!\d)"), "[ACCOUNT]"),
    # Phone numbers (7-10 digit patterns)
    (re.compile(r"(?<!\d)(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)?\d{3}[-.\s]?\d{4}(?!\d)"), "[PHONE]"),
    # Email addresses
    (re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"), "[EMAIL]"),
    # PINs / passwords
    (re.compile(r"(?i)(?:PIN|password|passcode|security\s*code)[:\s]*\d{4,8}"), "[PIN]"),
    # Street addresses
    (re.compile(r"\d{1,5}\s+(?:[A-Z][a-z]+\s+){1,4}(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Way|Blvd|Court|Ct|Circle|Cir)\b"), "[ADDRESS]"),
    # National IDs (SSN-like: XXX-XX-XXXX)
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[NATIONAL_ID]"),
    # Date of birth patterns
    (re.compile(r"(?i)(?:date\s+of\s+birth|DOB|born\s+on)[:\s]+\d{1,2}[/-]\d{1,2}[/-]\d{2,4}"), "[DOB]"),
]

# Secondary pass: contextual name redaction (after other patterns)
_NAME_CONTEXT = re.compile(
    r"(?i)(?:my\s+name\s+is|I\s+am|this\s+is|speaking\s+with)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)"
)


def redact(text: str) -> str:
    """Apply all redaction rules to text. Returns redacted string."""
    for pattern, tag in _RULES:
        text = pattern.sub(tag, text)
    # Contextual name redaction
    text = _NAME_CONTEXT.sub(lambda m: m.group(0).replace(m.group(1), "[NAME]"), text)
    return text


def redact_turn(speaker: str, text: str) -> str:
    """Redact a single turn. Speaker label is not redacted."""
    return redact(text)
