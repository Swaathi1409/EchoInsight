"""Tests using the 30 synthetic QA fixtures to verify scorer logic."""
from __future__ import annotations

import pytest

from backend.qa.scorer import score
from tests.fixtures.qa_fixtures import FIXTURES


def test_fixture_count():
    """Exactly 30 fixtures are defined."""
    assert len(FIXTURES) == 30


def test_all_fixtures_labeled():
    """Every fixture must be labeled synthetic_fixture and not claim to be real."""
    for f in FIXTURES:
        assert f["fixture_type"] == "synthetic_fixture", f"Fixture '{f.get('label')}' missing fixture_type"
        assert f["gold_status"] == "synthetic", f"Fixture '{f.get('label')}' missing gold_status"


@pytest.mark.parametrize("fixture", FIXTURES, ids=[f["label"] for f in FIXTURES])
def test_fixture_scorer(fixture):
    """Score each fixture; verify expected results where specified."""
    items = fixture["items"]
    result = score(items)

    # Basic shape
    assert "score" in result
    assert "coverage" in result
    assert "critical_violation" in result
    assert "items" in result
    assert 0 <= result["score"] <= 100
    assert 0.0 <= result["coverage"] <= 1.0

    # Check critical_violation expectation
    if "expected_critical_violation" in fixture:
        assert result["critical_violation"] == fixture["expected_critical_violation"], (
            f"[{fixture['label']}] expected critical_violation={fixture['expected_critical_violation']}, "
            f"got {result['critical_violation']}"
        )

    # Check exact score if specified
    if "expected_score" in fixture:
        assert result["score"] == fixture["expected_score"], (
            f"[{fixture['label']}] expected score={fixture['expected_score']}, got {result['score']}"
        )

    # Check score max if specified
    if "expected_score_max" in fixture:
        assert result["score"] <= fixture["expected_score_max"], (
            f"[{fixture['label']}] expected score <= {fixture['expected_score_max']}, got {result['score']}"
        )

    # Check exact coverage if specified
    if "expected_coverage" in fixture:
        assert abs(result["coverage"] - fixture["expected_coverage"]) < 0.01, (
            f"[{fixture['label']}] expected coverage={fixture['expected_coverage']}, got {result['coverage']}"
        )

    # Check coverage less than if specified
    if "expected_coverage_lt" in fixture:
        assert result["coverage"] < fixture["expected_coverage_lt"], (
            f"[{fixture['label']}] expected coverage < {fixture['expected_coverage_lt']}, got {result['coverage']}"
        )

    # Critical violation always caps score at 60
    if result["critical_violation"]:
        assert result["score"] <= 60, (
            f"[{fixture['label']}] critical violation but score={result['score']} > 60"
        )
