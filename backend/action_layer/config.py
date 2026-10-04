"""
backend/action_layer/config.py
Master switch and configuration for the Action Intelligence Layer.

ACTION_LAYER_ENABLED in .env (or env var) controls the gate.
act_settings DB table provides runtime toggle (also default false).
Both must be true for the layer to activate.
"""
from __future__ import annotations

# NOTE: Read from Settings (pydantic-settings) so .env is respected.
# Evaluated lazily via function to avoid circular imports at module load time.

def _env_flag() -> bool:
    try:
        from backend.config.settings import get_settings
        return get_settings().action_layer_enabled
    except Exception:
        import os
        return os.getenv("ACTION_LAYER_ENABLED", "false").strip().lower() in ("1", "true", "yes")


# Kept as a lazy property — call ACTION_LAYER_ENABLED_ENV() instead of reading as bool directly.
# For backward compat with existing code that uses it as a bool, we make it a property-like callable
# but actually replace all usages with the function call pattern below in guard.py.

# Module-level cached value (set once on first import of this module after server start)
import os as _os
_raw = _os.getenv("ACTION_LAYER_ENABLED", "false").strip().lower()
ACTION_LAYER_ENABLED_ENV: bool = _raw in ("1", "true", "yes")

# Default rule versions (labels are example/demonstration policies)
DEFAULT_RISK_RULES_VERSION = "risk_example_v1"
DEFAULT_PRIORITY_RULES_VERSION = "priority_example_v1"
DEFAULT_PLAYBOOK_RULES_VERSION = "playbook_example_v1"
DEFAULT_RECURRENCE_RULES_VERSION = "recurrence_example_v1"
DEFAULT_PREVENTION_RULES_VERSION = "prevention_example_v1"
DEFAULT_PHRASE_LISTS_VERSION = "phrase_lists_example_v1"

DEFAULT_COMMITMENT_DUE_SOON_HOURS = 24
MIN_N_FOR_COMPARISON = 5
MIN_N_FOR_DIAGNOSIS = 10
PDCA_MIN_POST_DAYS = 7
PDCA_MIN_POST_CONVERSATIONS = 10
DERIVE_JOB_INTERVAL_SECONDS = 3600

DISABLED_RESPONSE = {
    "enabled": False,
    "detail": "Action layer is disabled. Set ACTION_LAYER_ENABLED=true and enable via admin settings.",
}
