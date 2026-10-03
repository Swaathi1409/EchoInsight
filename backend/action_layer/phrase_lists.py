"""
backend/action_layer/phrase_lists.py
Versioned phrase lists for intent and urgency detection.

All phrase matching is case-insensitive substring or word-boundary.
These lists are "example policy" — labeled as such.
Version: phrase_lists_example_v1
"""
from __future__ import annotations

# ── Explicit switching / cancellation intent ───────────────────────────────────
CANCELLATION_INTENT_PHRASES = [
    "want to cancel", "wants to cancel", "cancel my", "cancel the",
    "canceling", "cancelling", "cancellation", "disconnect my",
    "disconnect the service", "terminate my", "terminate the",
    "switch to another", "switching to another", "moving to another",
    "going to switch", "going to leave", "leaving your service",
    "looking for another provider", "will be moving",
    "want to leave", "wants to leave", "port out", "porting out",
    "cancel account", "close my account", "close account",
]

# ── Price / billing sensitivity ────────────────────────────────────────────────
PRICE_SENSITIVE_PHRASES = [
    "too expensive", "cheaper", "cheaper option", "lower price",
    "reduce my bill", "reduce the bill", "discount", "promotion",
    "promotional rate", "offer", "better deal", "better offer",
    "competitor price", "competitor offer", "lower rate",
    "affordable", "cannot afford", "can't afford", "overcharged",
    "incorrect charge", "wrong charge", "billing error", "billing dispute",
    "refund", "credit to my account",
]

BILLING_REASON_PHRASES = [
    "bill", "billing", "charge", "invoice", "payment",
    "overcharged", "wrong amount", "incorrect amount",
]

# ── Relationship repair signals ────────────────────────────────────────────────
BROKEN_PROMISE_PHRASES = [
    "you promised", "they promised", "agent promised", "was supposed to",
    "said they would", "told me they would", "commitment was",
    "you said", "they said you would", "assured me",
    "never happened", "still waiting", "no one called back",
    "never received", "still not resolved",
]

ANGER_PHRASES = [
    "very upset", "extremely upset", "furious", "outraged", "unacceptable",
    "disgraceful", "terrible service", "awful service", "worst service",
    "never again", "disgusted", "fed up", "sick of this",
    "absolutely terrible", "completely unacceptable",
]

# ── Firm exit intent ───────────────────────────────────────────────────────────
FIRM_EXIT_PHRASES = [
    "final decision", "already decided", "made up my mind",
    "not interested in offers", "don't want any offers",
    "no offers please", "just want to cancel", "just cancel it",
    "nothing will change my mind", "done with this company",
    "not coming back", "won't be coming back",
]

DECLINED_OFFER_PHRASES = [
    "not interested", "no thank you", "no thanks", "declined",
    "don't want it", "doesn't help", "won't help",
]

# ── Time pressure signals ──────────────────────────────────────────────────────
TIME_PRESSURE_PHRASES = [
    "urgent", "urgently", "as soon as possible", "asap",
    "need this today", "need this now", "immediately",
    "cannot wait", "can't wait", "very important",
    "matter of urgency", "time sensitive", "deadline",
    "by end of day", "by tomorrow", "need it fixed now",
]

# ── High-impact reasons (example list, admin-configurable) ────────────────────
DEFAULT_HIGH_IMPACT_REASONS = [
    "network outage",
    "billing dispute",
    "cancellation intent",
    "service termination",
    "escalation",
    "repeat contact",
    "broken promise",
    "no service",
    "data breach",
    "complaint",
]


def find_matching_phrases(text: str, phrase_list: list[str]) -> list[str]:
    """Return all phrases from phrase_list found in text (case-insensitive)."""
    text_lower = text.lower()
    return [p for p in phrase_list if p.lower() in text_lower]


PHRASE_LISTS_VERSION = "phrase_lists_example_v1"
PHRASE_LISTS_LABEL = "example policy — owner review required before production use"
