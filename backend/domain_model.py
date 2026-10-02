# domain_model.py
# Core domain model: enums, constants, and shared type definitions.
# These are used across all backend packages.
# No package-level imports to prevent circular dependencies.
"""Core domain model enums and type definitions for EchoInsight."""
from __future__ import annotations

from enum import Enum


class SpeakerRole(str, Enum):
    AGENT = "agent"
    CUSTOMER = "customer"
    UNKNOWN = "unknown"
    SYSTEM = "system"


class ConversationStatus(str, Enum):
    CREATED = "created"
    ACTIVE = "active"
    ENDED = "ended"
    # Tier 2:
    RESUMED = "resumed"
    CLOSED = "closed"


class ConversationEndReason(str, Enum):
    NORMAL = "normal"
    ABANDONED = "abandoned"
    TRANSFER = "transfer"
    ESCALATION = "escalation"
    IDLE_TIMEOUT = "idle_timeout"
    UNKNOWN = "unknown"


class TurnExtractionStatus(str, Enum):
    PENDING = "pending"
    DONE = "done"
    FAILED = "failed"


class CallReason(str, Enum):
    NETWORK_COVERAGE_OR_DROPPED_CALLS = "network_coverage_or_dropped_calls"
    MOBILE_DATA_ISSUE = "mobile_data_issue"
    INTERNET_OR_BROADBAND_OUTAGE = "internet_or_broadband_outage"
    BILLING_DISPUTE = "billing_dispute"
    PLAN_CHANGE_OR_UPGRADE = "plan_change_or_upgrade"
    CANCELLATION_OR_CHURN_INTENT = "cancellation_or_churn_intent"
    ROAMING_OR_INTERNATIONAL = "roaming_or_international"
    SIM_OR_ACTIVATION = "sim_or_activation"
    DEVICE_ISSUE = "device_issue"
    TECHNICAL_VISIT = "technical_visit"
    ACCOUNT_ACCESS_OR_SECURITY = "account_access_or_security"
    COMPLAINT_OR_ESCALATION = "complaint_or_escalation"
    GENERAL_INQUIRY = "general_inquiry"
    PAYMENT_OR_TOP_UP = "payment_or_top_up"


class CustomerSentiment(str, Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    FRUSTRATED = "frustrated"
    ANGRY = "angry"


class ResolutionStatus(str, Enum):
    RESOLVED = "resolved"
    PARTIALLY_RESOLVED = "partially_resolved"
    PENDING = "pending"
    UNRESOLVED = "unresolved"
    ESCALATED = "escalated"
    UNKNOWN = "unknown"


class ChurnRisk(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class CommitmentStatus(str, Enum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    UNCERTAIN = "uncertain"


class ActionEventType(str, Enum):
    CREATE = "create"
    ACCEPT = "accept"
    SCHEDULE = "schedule"
    COMPLETE = "complete"
    CANCEL = "cancel"
    RETRACT = "retract"


class QACheckItemId(str, Enum):
    GREETING = "greeting"
    IDENTITY_VERIFICATION = "identity_verification"
    EMPATHY = "empathy"
    DISCLOSURE = "disclosure"
    PROHIBITED_PROMISES = "prohibited_promises"
    CLOSURE = "closure"


class QACheckResult(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    NOT_APPLICABLE = "not_applicable"
    NEEDS_REVIEW = "needs_review"


class FindingType(str, Enum):
    POTENTIAL_CONCERN = "potential_concern"
    CONFIRMED_VIOLATION = "confirmed_violation"


class EvidenceType(str, Enum):
    QUOTE = "quote"
    ABSENCE = "absence"


class ValidationErrorCategory(str, Enum):
    INVALID_MODEL_JSON = "invalid_model_json"
    UNSUPPORTED_EVIDENCE = "unsupported_evidence"
    INCONSISTENT_STATE = "inconsistent_state"
    PROVIDER_TIMEOUT = "provider_timeout"
    PROVIDER_RATE_LIMITED = "provider_rate_limited"
    SCHEMA_VALIDATION_FAILED = "schema_validation_failed"
    NONEXISTENT_TURN_ID = "nonexistent_turn_id"
    QUOTE_MISMATCH = "quote_mismatch"
    LABEL_OUT_OF_TAXONOMY = "label_out_of_taxonomy"


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobType(str, Enum):
    FINAL_ANALYSIS = "final_analysis"
    PER_TURN_EXTRACTION = "per_turn_extraction"
    CATCHUP_EXTRACTION = "catchup_extraction"


class UserRole(str, Enum):
    ADMIN = "admin"
    SUPERVISOR = "supervisor"
    AGENT = "agent"


class VerificationResult(str, Enum):
    SUPPORTED = "supported"
    NOT_SUPPORTED = "not_supported"
    INSUFFICIENT = "insufficient"


# Synthetic agent/team assignment constants
NUM_AGENTS = 25
NUM_TEAMS = 5
AGENTS_PER_TEAM = NUM_AGENTS // NUM_TEAMS  # 5

# Evidence gate constants
EVIDENCE_QUOTE_MIN_LENGTH = 3  # minimum length of an exact quote (chars)
EVIDENCE_WHITESPACE_NORMALIZE = True  # normalize whitespace when comparing quotes

# Turn ID format
TURN_ID_FORMAT = "turn_{seq:04d}"

# Analysis versions
ANALYSIS_PROVISIONAL_FLAG = True
ANALYSIS_FINAL_FLAG = False

# Default QA coverage threshold
DEFAULT_COVERAGE_THRESHOLD = 0.70

# Default critical violation score cap
DEFAULT_CRITICAL_VIOLATION_SCORE_CAP = 60

# Long call threshold (turns)
LONG_CALL_TURN_THRESHOLD = 40
LONG_CALL_WINDOW_SIZE = 40
LONG_CALL_WINDOW_OVERLAP = 5

# Idle timeout (Tier 2)
DEFAULT_IDLE_TIMEOUT_MINUTES = 30

# Resume window (Tier 2)
DEFAULT_RESUME_WINDOW_HOURS = 72

# Segment gap threshold (Tier 2)
DEFAULT_SEGMENT_GAP_MINUTES = 10
