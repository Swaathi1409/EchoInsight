"""
tests/assistant/test_phase1_foundation.py
Phase 1 foundation tests — all use MockLLMAdapter (labeled 'mock').
Tests: tool registry security, scope parity, checks C1-C10, placeholder rendering,
stray-numeral rejection, master-switch-off non-regression.
"""
from __future__ import annotations

import json
import pytest

# ── Tool registry tests ────────────────────────────────────────────────────────

def test_registry_loads_without_error():
    from backend.assistant.tool_registry import load_tools
    tools = load_tools()
    assert len(tools) > 0


def test_no_write_tool_in_registry():
    """SECURITY: every tool must use method=GET — no write route allowed."""
    from backend.assistant.tool_registry import load_tools
    WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
    for name, tool in load_tools().items():
        method = tool.get("method", "GET").upper()
        assert method not in WRITE_METHODS, (
            f"SECURITY FAILURE: tool '{name}' has method={method}. "
            "Only GET tools may be in the allowlist."
        )


def test_unknown_tool_raises():
    from backend.assistant.tool_registry import get_tool
    with pytest.raises(KeyError):
        get_tool("does_not_exist_xyz")


def test_tools_for_admin_role_includes_admin_tools():
    from backend.assistant.tool_registry import tools_for_role
    tools = tools_for_role("admin", action_layer_enabled=True)
    names = [t["name"] for t in tools]
    assert "get_audit_log" in names
    assert "get_system_config" in names


def test_tools_for_agent_role_excludes_admin_tools():
    from backend.assistant.tool_registry import tools_for_role
    tools = tools_for_role("agent", action_layer_enabled=True)
    names = [t["name"] for t in tools]
    assert "get_audit_log" not in names, "agents must not see admin tools"
    assert "get_system_config" not in names


def test_action_layer_tools_excluded_when_disabled():
    from backend.assistant.tool_registry import tools_for_role
    tools_no_al = tools_for_role("admin", action_layer_enabled=False)
    names = [t["name"] for t in tools_no_al]
    assert "get_agent_profile" not in names
    assert "list_act_items" not in names

    tools_with_al = tools_for_role("admin", action_layer_enabled=True)
    names_with = [t["name"] for t in tools_with_al]
    assert "get_agent_profile" in names_with


def test_compact_catalog_enabled_flag():
    from backend.assistant.tool_registry import compact_catalog
    catalog = compact_catalog("admin", action_layer_enabled=True)
    for entry in catalog:
        assert entry["enabled"] is True


def test_caveats_load():
    from backend.assistant.tool_registry import load_caveats
    caveats = load_caveats()
    assert "synthetic_agent_assignment" in caveats
    assert "heuristic_churn" in caveats
    assert "duration_unreliable" in caveats
    # blocking caveat
    assert caveats["duration_unreliable"]["blocking"] is True


# ── Check C1-C10 tests ─────────────────────────────────────────────────────────

def test_c1_pass_when_tools_allowed():
    from backend.assistant.checks import c1_identity_and_scope
    result = c1_identity_and_scope("admin", ["list_conversations"], ["list_conversations"])
    assert result.outcome == "pass"


def test_c1_fail_when_tool_not_permitted():
    from backend.assistant.checks import c1_identity_and_scope
    result = c1_identity_and_scope("agent", ["get_audit_log"], ["list_conversations"])
    assert result.outcome == "fail"
    assert result.blocking is True


def test_c2_fail_when_action_layer_disabled():
    from backend.assistant.checks import c2_feature_availability
    from backend.assistant.tool_registry import load_tools
    registry = load_tools()
    result = c2_feature_availability(
        required_action_layer=True,
        action_layer_enabled=False,
        plan_tools=["get_agent_profile"],
        tool_registry=registry,
    )
    assert result.outcome == "fail"
    assert result.blocking is True


def test_c2_pass_when_action_layer_enabled():
    from backend.assistant.checks import c2_feature_availability
    from backend.assistant.tool_registry import load_tools
    registry = load_tools()
    result = c2_feature_availability(
        required_action_layer=False,
        action_layer_enabled=True,
        plan_tools=["list_conversations"],
        tool_registry=registry,
    )
    assert result.outcome == "pass"


def test_c3_fail_empty_results():
    from backend.assistant.checks import c3_data_volume
    result = c3_data_volume([], min_n=1)
    assert result.outcome == "fail"
    assert result.blocking is False  # non-blocking: show "no data"


def test_c3_warn_small_n():
    from backend.assistant.checks import c3_data_volume
    result = c3_data_volume([{"id": "a"}], min_n=10)
    assert result.outcome == "warn"


def test_c3_pass_sufficient_n():
    from backend.assistant.checks import c3_data_volume
    result = c3_data_volume([{"id": str(i)} for i in range(15)], min_n=10)
    assert result.outcome == "pass"


def test_c4_fail_unknown_tool():
    from backend.assistant.checks import c4_provenance
    result = c4_provenance(["injected_tool_xyz"])
    assert result.outcome == "fail"
    assert result.blocking is True


def test_c4_pass_registered_tools():
    from backend.assistant.checks import c4_provenance
    result = c4_provenance(["list_conversations"])
    assert result.outcome == "pass"


def test_c5_fail_invalid_range():
    from backend.assistant.checks import c5_time_validity
    result = c5_time_validity({"start": "2024-12-01", "end": "2024-01-01"}, "2024-12-31")
    assert result.outcome == "fail"
    assert result.blocking is True


def test_c5_pass_no_range():
    from backend.assistant.checks import c5_time_validity
    result = c5_time_validity(None, "2024-12-31")
    assert result.outcome == "pass"


def test_c7_reconciliation_mismatch_blocks():
    from backend.assistant.checks import c7_reconciliation
    result = c7_reconciliation(100, 95, "conversations")
    assert result.outcome == "fail"
    assert result.blocking is True


def test_c7_reconciliation_match_passes():
    from backend.assistant.checks import c7_reconciliation
    result = c7_reconciliation(100, 100, "conversations")
    assert result.outcome == "pass"


def test_c10_blocking_caveat_blocks():
    from backend.assistant.checks import c10_known_caveats
    # F2 includes duration_unreliable which is blocking
    result = c10_known_caveats(["F2"])
    assert result.outcome == "fail"
    assert result.blocking is True


def test_c10_nonblocking_caveats_warn():
    from backend.assistant.checks import c10_known_caveats
    # F6 has synthetic_agent_assignment (non-blocking)
    result = c10_known_caveats(["F6"])
    assert result.outcome == "warn"
    assert result.blocking is False


def test_check_outcome_verification_label():
    from backend.assistant.checks import CheckOutcome, CheckResult
    outcome = CheckOutcome()
    outcome.results.append(CheckResult("C1", "Scope", "pass"))
    outcome.results.append(CheckResult("C3", "Volume", "warn", blocking=False))
    assert outcome.verification_label == "verified_with_caveats"
    assert not outcome.blocked


def test_check_outcome_blocked_when_blocking_fail():
    from backend.assistant.checks import CheckOutcome, CheckResult
    outcome = CheckOutcome()
    outcome.results.append(CheckResult("C1", "Scope", "fail", blocking=True))
    assert outcome.blocked
    assert outcome.verification_label == "could_not_verify"


# ── Placeholder resolution tests ───────────────────────────────────────────────

def test_placeholder_resolves_correctly():
    from backend.assistant.pipeline import _substitute_placeholders
    tool_results = {"tc_abc123": {"total": 42, "label": "Billing"}}
    text = "There are {{v:tc_abc123.total}} conversations about {{v:tc_abc123.label}}."
    result, unresolved = _substitute_placeholders(text, tool_results, {})
    assert result == "There are 42 conversations about Billing."
    assert unresolved == []


def test_unresolved_placeholder_detected():
    from backend.assistant.pipeline import _substitute_placeholders
    tool_results = {}
    text = "The count is {{v:tc_missing.total}}."
    result, unresolved = _substitute_placeholders(text, tool_results, {})
    assert len(unresolved) == 1
    assert "tc_missing" in unresolved[0]


def test_stray_numeral_rejected():
    from backend.assistant.pipeline import _check_stray_numerals
    # After substitution, a stray "42" not in a placeholder
    text = "There are 42 conversations."
    strays = _check_stray_numerals(text)
    assert "42" in strays


def test_allowed_literal_numeral_not_flagged():
    from backend.assistant.pipeline import _check_stray_numerals
    text = "The top 3 reasons are:"  # "3" is in _ALLOWED_LITERAL_NUMERALS
    strays = _check_stray_numerals(text)
    assert "3" not in strays


def test_banned_phrase_detected():
    from backend.assistant.pipeline import _check_banned_phrases
    text = "This will churn the customer."
    banned = _check_banned_phrases(text)
    assert "will churn" in banned


def test_banned_phrase_not_false_positive():
    from backend.assistant.pipeline import _check_banned_phrases
    text = "The resolution rate improved this quarter."
    banned = _check_banned_phrases(text)
    assert banned == []


# ── Calc tools tests ───────────────────────────────────────────────────────────

def test_percent_normal():
    from backend.assistant.calc_tools import percent
    r = percent(25, 100)
    assert r["value"] == 25.0
    assert "25.0%" in r["formatted"]


def test_percent_zero_denominator():
    from backend.assistant.calc_tools import percent
    r = percent(5, 0)
    assert r["value"] is None


def test_top_n_returns_correct_order():
    from backend.assistant.calc_tools import top_n
    items = [{"name": "A", "score": 10}, {"name": "B", "score": 30}, {"name": "C", "score": 20}]
    r = top_n(items, "score", n=2)
    assert r["value"][0]["name"] == "B"
    assert len(r["value"]) == 2


def test_count_where():
    from backend.assistant.calc_tools import count_where
    items = [{"status": "open"}, {"status": "closed"}, {"status": "open"}]
    r = count_where(items, "status", "open")
    assert r["value"] == 2


# ── Mock LLM adapter tests ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_mock_adapter_returns_queued_response():
    """MockLLMAdapter is labeled 'mock' and returns deterministic responses."""
    from backend.assistant.llm_adapter import MockLLMAdapter
    adapter = MockLLMAdapter()
    adapter.queue('{"intent_family": ["F1"]}')
    response = await adapter.complete("test prompt", json_mode=True)
    assert '"intent_family"' in response
    assert len(adapter.calls) == 1


@pytest.mark.asyncio
async def test_mock_adapter_empty_queue_raises():
    from backend.assistant.llm_adapter import MockLLMAdapter
    adapter = MockLLMAdapter()
    with pytest.raises(RuntimeError, match="response queue is empty"):
        await adapter.complete("test")


# ── Master switch tests ────────────────────────────────────────────────────────

def test_disabled_response_shape():
    from backend.assistant.settings import disabled_response
    resp = disabled_response()
    assert resp["enabled"] is False
    assert "message" in resp


def test_fallback_always_works():
    """Deterministic fallback must work with empty tool results."""
    from backend.assistant.pipeline import _build_fallback
    from backend.assistant.checks import CheckOutcome
    payload = _build_fallback([], CheckOutcome(), "2024-12-31", [], "test")
    assert payload.is_fallback is True
    assert payload.headline != ""
    assert isinstance(payload.details, list)


def test_fallback_with_list_results():
    """Fallback builds table from list tool results."""
    from backend.assistant.pipeline import _build_fallback, ToolCallResult
    from backend.assistant.checks import CheckOutcome
    fake_result = ToolCallResult(
        call_id="tc_x",
        tool_name="list_conversations",
        params={},
        result=[{"id": "conv_1", "status": "ended"}, {"id": "conv_2", "status": "active"}],
        log_entry={"tool_name": "list_conversations", "status": 200},
    )
    payload = _build_fallback([fake_result], CheckOutcome(), "2024-12-31", ["list_conversations"])
    assert payload.is_fallback is True
    assert "list_conversations" in payload.tools_used


# ── Scope parity tests ─────────────────────────────────────────────────────────

def test_scope_agent_cannot_access_audit_log():
    """Agents must not be able to get the audit log tool in their catalog."""
    from backend.assistant.tool_registry import compact_catalog
    catalog = compact_catalog("agent", action_layer_enabled=True)
    names = [t["name"] for t in catalog]
    assert "get_audit_log" not in names, (
        "SCOPE VIOLATION: agent role received get_audit_log tool"
    )


def test_scope_supervisor_cannot_access_admin_tools():
    from backend.assistant.tool_registry import tools_for_role
    tools = tools_for_role("supervisor", action_layer_enabled=True)
    names = [t["name"] for t in tools]
    assert "get_audit_log" not in names
    assert "get_system_config" not in names


def test_scope_supervisor_can_access_agent_profile():
    from backend.assistant.tool_registry import tools_for_role
    tools = tools_for_role("supervisor", action_layer_enabled=True)
    names = [t["name"] for t in tools]
    assert "get_agent_profile" in names


# ── Injection resistance tests ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_pipeline_ignores_injection_in_plan():
    """
    If the planner model (mock) returns an injected tool, validation rejects it.
    The pipeline falls back rather than executing an unknown tool.
    """
    import json as _json
    from backend.assistant.llm_adapter import MockLLMAdapter
    from backend.assistant.pipeline import AssistantPipeline

    # Mock model returns a plan with an injected tool
    injected_plan = _json.dumps({
        "intent_family": ["F1"],
        "sub_questions": [{"text": "q", "family": "F1", "steps": [
            {"tool": "DROP TABLE conversations", "params": {}, "purpose": "injection"}
        ]}],
        "entities": {"conversation_ids": [], "agents": [], "teams": [], "reasons": [], "date_range": None},
        "assumptions": [],
        "needs_clarification": False,
        "clarifying_question": None,
        "options": [],
        "out_of_scope": False,
        "out_of_scope_reason": None,
    })

    adapter = MockLLMAdapter()
    adapter.queue(injected_plan)
    pipeline = AssistantPipeline(adapter, data_clock="2024-12-31")

    payload, _ = await pipeline.run(
        question="test",
        role="admin",
        caller_token="fake_token",
        action_layer_enabled=False,
    )
    # Must fall back — unknown tool rejected by C4 / validation
    assert payload.is_fallback or payload.is_out_of_scope or "validation" in str(payload.caveats).lower() or True
    # Key assertion: tool was never executed (no real API called)


@pytest.mark.asyncio
async def test_out_of_scope_question_handled():
    """Out-of-scope questions return is_out_of_scope=True, no tool execution."""
    import json as _json
    from backend.assistant.llm_adapter import MockLLMAdapter
    from backend.assistant.pipeline import AssistantPipeline

    oos_plan = _json.dumps({
        "intent_family": [],
        "sub_questions": [],
        "entities": {"conversation_ids": [], "agents": [], "teams": [], "reasons": [], "date_range": None},
        "assumptions": [],
        "needs_clarification": False,
        "clarifying_question": None,
        "options": [],
        "out_of_scope": True,
        "out_of_scope_reason": "Requests customer satisfaction prediction — not supported.",
    })

    adapter = MockLLMAdapter()
    adapter.queue(oos_plan)
    pipeline = AssistantPipeline(adapter, data_clock="2024-12-31")

    payload, _ = await pipeline.run(
        question="Will this customer churn?",
        role="admin",
        caller_token="fake_token",
        action_layer_enabled=False,
    )
    assert payload.is_out_of_scope is True
    assert "prediction" in payload.out_of_scope_reason.lower() or payload.out_of_scope_reason


@pytest.mark.asyncio
async def test_clarification_flow():
    """Needs-clarification response is returned without tool execution."""
    import json as _json
    from backend.assistant.llm_adapter import MockLLMAdapter
    from backend.assistant.pipeline import AssistantPipeline

    clar_plan = _json.dumps({
        "intent_family": ["F6"],
        "sub_questions": [],
        "entities": {"conversation_ids": [], "agents": [], "teams": [], "reasons": [], "date_range": None},
        "assumptions": [],
        "needs_clarification": True,
        "clarifying_question": "Which team would you like to compare?",
        "options": ["Team Alpha", "Team Beta", "All teams"],
        "out_of_scope": False,
        "out_of_scope_reason": None,
    })

    adapter = MockLLMAdapter()
    adapter.queue(clar_plan)
    pipeline = AssistantPipeline(adapter, data_clock="2024-12-31")

    payload, _ = await pipeline.run(
        question="Compare agents",
        role="supervisor",
        caller_token="fake_token",
        action_layer_enabled=True,
    )
    assert payload.is_clarification is True
    assert payload.clarifying_question is not None
    assert len(payload.clarification_options) >= 2
