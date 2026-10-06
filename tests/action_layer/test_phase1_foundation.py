"""
tests/action_layer/test_phase1_foundation.py

Phase 1 tests:
1. Master switch OFF (default): /api/v1/action/status returns {"enabled": false}
2. Master switch OFF: every disabled endpoint returns {"enabled": false}
3. Migration up/down is verified by the migration file structure (not re-running on test DB)
4. Repository imports cleanly without circular dependencies
5. No existing test is broken (verified by running the full suite)
"""
from __future__ import annotations

import pytest

from tests.conftest import get_token

# ── Import smoke tests ────────────────────────────────────────────────────────

def test_action_layer_config_imports():
    """Config module imports without errors."""
    from backend.action_layer.config import (
        ACTION_LAYER_ENABLED_ENV,
        DEFAULT_RISK_RULES_VERSION,
        DISABLED_RESPONSE,
    )
    assert isinstance(ACTION_LAYER_ENABLED_ENV, bool)
    assert "risk_example_v1" in DEFAULT_RISK_RULES_VERSION
    assert DISABLED_RESPONSE["enabled"] is False


def test_action_layer_models_import():
    """All act_* ORM models import and have correct table names."""
    from backend.action_layer.models import (
        ActDraft,
        ActInitiative,
        ActInitiativeEvent,
        ActItem,
        ActItemEvent,
        ActPreventionSuggestion,
        ActRecommendation,
        ActRecurringIssue,
        ActRulesVersion,
        ActSettings,
    )
    expected_tables = {
        "act_settings", "act_rules_version", "act_items", "act_item_events",
        "act_recommendations", "act_drafts", "act_recurring_issues",
        "act_prevention_suggestions", "act_initiatives", "act_initiative_events",
    }
    actual_tables = {
        ActSettings.__tablename__, ActRulesVersion.__tablename__,
        ActItem.__tablename__, ActItemEvent.__tablename__,
        ActRecommendation.__tablename__, ActDraft.__tablename__,
        ActRecurringIssue.__tablename__, ActPreventionSuggestion.__tablename__,
        ActInitiative.__tablename__, ActInitiativeEvent.__tablename__,
    }
    assert expected_tables == actual_tables


def test_repository_imports():
    """CoreRepository imports without errors."""
    from backend.action_layer.repository import CoreRepository
    assert CoreRepository is not None


def test_guard_imports():
    """Guard module imports without errors."""
    from backend.action_layer.guard import disabled_response
    response = disabled_response()
    # Should return a JSONResponse with enabled=false
    import json
    data = json.loads(response.body)
    assert data["enabled"] is False


def test_action_layer_disabled_env():
    """With ACTION_LAYER_ENABLED not set, env flag is False."""
    from backend.action_layer.config import ACTION_LAYER_ENABLED_ENV
    # In test environment ACTION_LAYER_ENABLED is not set, so this must be False
    # (tests are run without the env var)
    assert ACTION_LAYER_ENABLED_ENV is False


def test_act_tables_in_base_metadata():
    """All act_* tables appear in Base.metadata after importing action layer models."""
    import backend.action_layer.models
    from backend.models import Base
    table_names = set(Base.metadata.tables.keys())
    act_tables = {t for t in table_names if t.startswith("act_")}
    assert len(act_tables) == 10, f"Expected 10 act_* tables, got {len(act_tables)}: {act_tables}"


# ── HTTP endpoint tests ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_action_status_disabled(admin_client):
    """
    /api/v1/action/status returns {"enabled": false} when ACTION_LAYER_ENABLED is not set.
    Uses the existing test client which authenticates as admin.
    """
    response = await admin_client.get("/api/v1/action/status")
    assert response.status_code == 200
    data = response.json()
    assert data["enabled"] is False


@pytest.mark.asyncio
async def test_action_items_disabled(admin_client):
    """When disabled, /api/v1/action/items returns disabled response (auth required)."""
    token = await get_token(admin_client)
    headers = {"Authorization": f"Bearer {token}"}
    response = await admin_client.get("/api/v1/action/items", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["enabled"] is False


@pytest.mark.asyncio
async def test_action_issues_disabled(admin_client):
    """When disabled, /api/v1/action/issues returns disabled response."""
    token = await get_token(admin_client)
    headers = {"Authorization": f"Bearer {token}"}
    response = await admin_client.get("/api/v1/action/issues", headers=headers)
    assert response.status_code == 200
    assert response.json()["enabled"] is False


@pytest.mark.asyncio
async def test_action_initiatives_disabled(admin_client):
    """When disabled, /api/v1/action/initiatives returns disabled response."""
    token = await get_token(admin_client)
    headers = {"Authorization": f"Bearer {token}"}
    response = await admin_client.get("/api/v1/action/initiatives", headers=headers)
    assert response.status_code == 200
    assert response.json()["enabled"] is False


@pytest.mark.asyncio
async def test_action_agent_profile_disabled(admin_client):
    """When disabled, /api/v1/action/agents profile returns disabled response."""
    token = await get_token(admin_client)
    headers = {"Authorization": f"Bearer {token}"}
    response = await admin_client.get("/api/v1/action/agents/agent-001/profile", headers=headers)
    assert response.status_code == 200
    assert response.json()["enabled"] is False
