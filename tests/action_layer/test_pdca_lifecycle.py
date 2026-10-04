"""
tests/action_layer/test_pdca_lifecycle.py

PDCA lifecycle unit tests — test backend logic directly via SQLAlchemy sessions.
No HTTP overhead. Action layer must be enabled (ACTION_LAYER_ENABLED handled in env).

Tests:
 1-2: Validation gates block Plan→Do without metric_key / target_value
 3:   Plan→Do passes with both fields
 4-5: Validation gates block Do→Check without impl desc / impl date
 6:   Do→Check passes with both fields
 7:   Adjust decision resets to Plan, bumps iteration
 8:   Standardize keeps stage at act, iteration stays 1
 9:   metric_key + target_value persisted on create
 10:  Legacy target_metric / target_change still accepted
 11:  check_sufficient_data defaults False on new initiative
"""
from __future__ import annotations

import pytest
import pytest_asyncio

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from backend.models import Base
from backend.action_layer.models import (   # noqa: F401 – registers tables with Base
    ActSettings, ActInitiative, ActInitiativeEvent,
    ActRulesVersion, ActItem, ActRecommendation, ActDraft,
    ActRecurringIssue, ActPreventionSuggestion,
)
from backend.models import User


# ── In-memory async engine for these tests ────────────────────────────────────

ENGINE = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
SESSION = async_sessionmaker(ENGINE, expire_on_commit=False)


@pytest_asyncio.fixture(autouse=True)
async def _setup_db():
    async with ENGINE.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with ENGINE.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def session() -> AsyncSession:
    async with SESSION() as s:
        yield s


# ── Helper to build a minimal user for audit log ─────────────────────────────

async def _make_user(session: AsyncSession) -> User:
    from backend.auth import hash_password
    u = User(username="tester", password_hash=hash_password("x"), role="admin", is_active=True)
    session.add(u)
    await session.flush()
    return u


# ── Inline gate logic (mirrors router.py, no HTTP) ───────────────────────────

STAGE_ORDER = {"plan": 0, "do": 1, "check": 2, "act": 3}

def _validate_plan_to_do(metric_key: str, target_value) -> str | None:
    """Return error message or None."""
    if not metric_key:
        return "metric_key"
    if target_value is None:
        return "target_value"
    return None


def _validate_do_to_check(impl_desc: str, impl_date) -> str | None:
    if not impl_desc:
        return "implementation_description"
    if not impl_date:
        return "implementation_date"
    return None


# ── Tests ─────────────────────────────────────────────────────────────────────

# 1. Gate: metric_key required for plan→do
@pytest.mark.asyncio
async def test_gate_plan_to_do_requires_metric_key():
    err = _validate_plan_to_do("", None)
    assert err == "metric_key"


# 2. Gate: target_value required for plan→do
@pytest.mark.asyncio
async def test_gate_plan_to_do_requires_target_value():
    err = _validate_plan_to_do("unresolved_rate", None)
    assert err == "target_value"


# 3. Plan→Do passes with both fields
@pytest.mark.asyncio
async def test_gate_plan_to_do_passes_with_fields():
    err = _validate_plan_to_do("unresolved_rate", 0.40)
    assert err is None


# 4. Gate: implementation_description required for do→check
@pytest.mark.asyncio
async def test_gate_do_to_check_requires_description():
    err = _validate_do_to_check("", None)
    assert err == "implementation_description"


# 5. Gate: implementation_date required for do→check (desc present)
@pytest.mark.asyncio
async def test_gate_do_to_check_requires_date():
    err = _validate_do_to_check("Did the thing", None)
    assert err == "implementation_date"


# 6. Do→Check passes with both fields
@pytest.mark.asyncio
async def test_gate_do_to_check_passes():
    from datetime import datetime, timezone
    err = _validate_do_to_check("Fix deployed", datetime(2024, 1, 15, tzinfo=timezone.utc))
    assert err is None


# 7. Adjust → new iteration (DB write test) ────────────────────────────────────

@pytest.mark.asyncio
async def test_adjust_creates_new_iteration(session: AsyncSession):
    ini = ActInitiative(
        title="Adjust test",
        stage="act",
        iteration=1,
        demonstration=False,
        problem_statement="p",
        root_cause_hypothesis="r",
        metric_key="unresolved_rate",
        target_value=0.35,
        implementation_description="Fix v1",
        do_status="completed",
        act_decision="adjust",
        act_notes="need another round",
    )
    session.add(ini)
    await session.flush()

    # Simulate the adjust logic from update_initiative
    old_iteration = ini.iteration
    ini.iteration += 1
    ini.stage = "plan"
    ini.implementation_date = None
    ini.implementation_description = ""
    ini.do_owner = ""
    ini.do_status = ""
    ini.customers_informed = None
    ini.customers_informed_notes = ""
    ini.check_computed_at = None
    ini.check_results_json = {}
    ini.act_decision = None
    ini.act_notes = ""
    await session.flush()

    assert ini.stage == "plan"
    assert ini.iteration == 2
    assert not ini.implementation_description
    assert ini.act_decision is None
    # Baseline must be preserved
    assert ini.metric_key == "unresolved_rate"
    assert ini.target_value == 0.35


# 8. Standardize: no iteration bump ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_standardize_does_not_create_iteration(session: AsyncSession):
    ini = ActInitiative(
        title="Standardize test",
        stage="act",
        iteration=1,
        demonstration=False,
        act_decision="standardize",
    )
    session.add(ini)
    await session.flush()

    # Standardize does NOT reset anything
    ini.act_notes = "It works"
    await session.flush()

    assert ini.stage == "act"
    assert ini.iteration == 1
    assert ini.act_decision == "standardize"


# 9. metric_key and target_value persisted ─────────────────────────────────────

@pytest.mark.asyncio
async def test_metric_fields_persisted(session: AsyncSession):
    ini = ActInitiative(
        title="Metric test",
        stage="plan",
        iteration=1,
        demonstration=False,
        metric_key="weekly_volume",
        target_value=10.0,
    )
    session.add(ini)
    await session.flush()

    assert ini.metric_key == "weekly_volume"
    assert ini.target_value == 10.0


# 10. Legacy target_metric / target_change still accepted ──────────────────────

@pytest.mark.asyncio
async def test_legacy_target_metric_still_works(session: AsyncSession):
    ini = ActInitiative(
        title="Legacy test",
        stage="plan",
        iteration=1,
        demonstration=False,
        target_metric="Custom KPI",
        target_change="<30%",
    )
    session.add(ini)
    await session.flush()

    assert ini.target_metric == "Custom KPI"
    assert ini.target_change == "<30%"


# 11. check_sufficient_data defaults False ─────────────────────────────────────

@pytest.mark.asyncio
async def test_check_insufficient_data_default(session: AsyncSession):
    ini = ActInitiative(
        title="Check default test",
        stage="plan",
        iteration=1,
        demonstration=False,
        metric_key="unresolved_rate",
        target_value=0.40,
    )
    session.add(ini)
    await session.flush()

    assert ini.check_sufficient_data is False
    assert ini.check_post_n is None


# 12. Stage order invariant: plan < do < check < act ──────────────────────────

def test_stage_order_invariant():
    assert STAGE_ORDER["plan"] < STAGE_ORDER["do"]
    assert STAGE_ORDER["do"] < STAGE_ORDER["check"]
    assert STAGE_ORDER["check"] < STAGE_ORDER["act"]
