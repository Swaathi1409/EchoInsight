"""
backend/action_layer/config.py
Master switch and configuration for the Action Intelligence Layer.

ACTION_LAYER_ENABLED env var (default false) controls compile-time gate.
act_settings DB table provides runtime toggle (also default false).
Both must be true for the layer to activate.
"""
from __future__ import annotations

import os

# ── Compile-time gate ────────────────────────────────────────────────────────
_ENV_FLAG = os.getenv("ACTION_LAYER_ENABLED", "false").strip().lower()
ACTION_LAYER_ENABLED_ENV: bool = _ENV_FLAG in ("1", "true", "yes")

# Default rule versions (labels are example/demonstration policies)
DEFAULT_RISK_RULES_VERSION = "risk_example_v1"
DEFAULT_PRIORITY_RULES_VERSION = "priority_example_v1"
DEFAULT_PLAYBOOK_RULES_VERSION = "playbook_example_v1"
DEFAULT_RECURRENCE_RULES_VERSION = "recurrence_example_v1"
DEFAULT_PREVENTION_RULES_VERSION = "prevention_example_v1"
DEFAULT_PHRASE_LISTS_VERSION = "phrase_lists_example_v1"

# Commitment urgency window (hours) — how soon is "due soon"
DEFAULT_COMMITMENT_DUE_SOON_HOURS = 24

# Minimum sample size for comparisons
MIN_N_FOR_COMPARISON = 5
MIN_N_FOR_DIAGNOSIS = 10

# PDCA check window requirements
PDCA_MIN_POST_DAYS = 7
PDCA_MIN_POST_CONVERSATIONS = 10

# Derive job schedule (cron-style interval in seconds, default 3600 = 1 hour)
DERIVE_JOB_INTERVAL_SECONDS = 3600

DISABLED_RESPONSE = {
    "enabled": False,
    "detail": "Action layer is disabled. Set ACTION_LAYER_ENABLED=true and enable via admin settings.",
}
