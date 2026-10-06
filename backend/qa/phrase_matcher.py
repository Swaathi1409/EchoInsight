"""
Deterministic keyword phrase matcher for QA policy checks.
Versioned phrase lists; supports negation handling and normalization.

This is the primary deterministic layer. The LLM QA scorer handles contextual
judgments (empathy, explanations). This matcher handles explicit policy phrases.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

MATCHER_VERSION = "v1"

# ---------------------------------------------------------------------------
# Phrase list definitions (versioned)
# ---------------------------------------------------------------------------

# Prohibited promise phrases: agent must NOT say these
PROHIBITED_PHRASES_V1: list[str] = [
    "i guarantee",
    "i can guarantee",
    "guaranteed to",
    "we guarantee",
    "100% sure",
    "100 percent sure",
    "definitely will",
    "promise you",
    "i promise",
    "no charge",            # without context (disclosure required)
    "no cost to you",
    "absolutely free",
    "you will receive",     # future promise without evidence
    "will be fixed by",
    "will be resolved by",
]

# Required disclosure trigger phrases: if agent performs these actions,
# they must also disclose the associated fee or policy.
DISCLOSURE_TRIGGERS_V1: list[str] = [
    "technician",
    "engineer visit",
    "home visit",
    "site visit",
    "send someone",
    "dispatch",
    "callout",
    "call out",
]

# Greeting phrases (any of these satisfy the greeting check)
GREETING_PHRASES_V1: list[str] = [
    "thank you for calling",
    "thanks for calling",
    "welcome to",
    "good morning",
    "good afternoon",
    "good evening",
    "hello, my name is",
    "hi, my name is",
    "hi my name is",
    "hello my name is",
    "this is",              # "this is [name] from..."
]

# Identity verification phrases
IDENTITY_VERIFY_PHRASES_V1: list[str] = [
    "verify your identity",
    "verify identity",
    "confirm your identity",
    "date of birth",
    "account number",
    "pin",
    "security question",
    "postcode",
    "zip code",
    "last four digits",
    "can i have your",
    "could i have your",
    "what is your",
    "please confirm your",
]

# Closure phrases
CLOSURE_PHRASES_V1: list[str] = [
    "is there anything else",
    "anything else i can help",
    "anything else i can do",
    "have a good day",
    "have a nice day",
    "take care",
    "goodbye",
    "thank you for calling",
    "thanks for calling",
    "thank you for your time",
]

# Negation patterns: if these precede a phrase in the same sentence,
# the phrase is considered negated and does NOT match.
NEGATION_PATTERNS: list[str] = [
    r"\b(cannot|can't|won't|will not|do not|don't|doesn't|is not|are not|isn't|aren't|never|no)\b"
]


# ---------------------------------------------------------------------------
# Core matcher
# ---------------------------------------------------------------------------

@dataclass
class PhraseMatchResult:
    matched: bool
    phrase: str = ""           # the phrase that matched
    turn_id: str = ""          # turn where the match was found
    quote: str = ""            # excerpt from the turn
    negated: bool = False      # True if the phrase was negated


def _normalize(text: str) -> str:
    """Lowercase and collapse whitespace."""
    return re.sub(r"\s+", " ", text).strip().lower()


def _is_negated(text: str, phrase: str) -> bool:
    """Return True if the phrase appears immediately after a negation pattern."""
    idx = text.lower().find(phrase)
    if idx < 0:
        return False
    # Check the 60 characters before the phrase for negation words
    before = text[max(0, idx - 60):idx]
    for pattern in NEGATION_PATTERNS:
        if re.search(pattern, before, re.IGNORECASE):
            return True
    return False


def match_any(
    phrases: list[str],
    turns: list[dict],  # list of {"turn_id": str, "speaker": str, "text": str}
    speaker_filter: str | None = None,
) -> PhraseMatchResult:
    """
    Search for any phrase in the turns list.
    Returns the first match found (or no-match result).
    """
    for turn in turns:
        if speaker_filter and turn.get("speaker") != speaker_filter:
            continue
        text = _normalize(turn.get("text", ""))
        for phrase in phrases:
            if phrase in text:
                negated = _is_negated(text, phrase)
                # Extract a short quote around the match
                idx = text.find(phrase)
                start = max(0, idx - 20)
                end = min(len(text), idx + len(phrase) + 20)
                quote = turn.get("text", "")[start:end].strip()
                return PhraseMatchResult(
                    matched=not negated,
                    phrase=phrase,
                    turn_id=turn.get("turn_id", ""),
                    quote=quote,
                    negated=negated,
                )
    return PhraseMatchResult(matched=False)


def check_prohibited_promises(turns: list[dict]) -> PhraseMatchResult:
    """Return first prohibited phrase found in agent turns (matched=True means violation)."""
    return match_any(PROHIBITED_PHRASES_V1, turns, speaker_filter="agent")


def check_greeting(turns: list[dict]) -> PhraseMatchResult:
    """Return True if agent greeted in any of the first 3 agent turns."""
    agent_turns = [t for t in turns if t.get("speaker") == "agent"]
    return match_any(GREETING_PHRASES_V1, agent_turns[:3])


def check_identity_verification(turns: list[dict]) -> PhraseMatchResult:
    """Return True if agent attempted identity verification."""
    return match_any(IDENTITY_VERIFY_PHRASES_V1, turns, speaker_filter="agent")


def check_disclosure_trigger(turns: list[dict]) -> PhraseMatchResult:
    """Return True if any disclosure trigger phrase was used (requiring a fee disclosure)."""
    return match_any(DISCLOSURE_TRIGGERS_V1, turns, speaker_filter="agent")


def check_closure(turns: list[dict]) -> PhraseMatchResult:
    """Return True if agent used a closure phrase in the last 4 agent turns."""
    agent_turns = [t for t in turns if t.get("speaker") == "agent"]
    return match_any(CLOSURE_PHRASES_V1, agent_turns[-4:])
