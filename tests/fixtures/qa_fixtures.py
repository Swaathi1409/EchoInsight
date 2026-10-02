"""
30 synthetic QA fixtures for scoring and evidence gate unit tests.
Each fixture is a dict with:
  - label: human-readable test scenario
  - fixture_type: "synthetic_fixture" (MUST be labeled)
  - gold_status: "synthetic" (not real data; not human-reviewed)
  - items: pre-annotated QA items (as LLM would return)
  - expected_*: assertions for the scorer output

These fixtures test the scorer's computation logic only.
They do NOT test LLM output quality — that requires the gold set and human annotation.
"""
from __future__ import annotations

FIXTURES: list[dict] = [
    # 1 - Perfect call
    {
        "label": "Perfect call: all items pass",
        "fixture_type": "synthetic_fixture", "gold_status": "synthetic",
        "items": [
            {"item_id": "greeting",              "result": "pass",           "explanation": "Greeted with name and company.", "quote": "Thank you for calling Union Mobile, my name is Alex"},
            {"item_id": "identity_verification", "result": "pass",           "explanation": "PIN verified before account action.", "quote": "verify your account with your PIN"},
            {"item_id": "empathy",               "result": "not_applicable", "explanation": "Customer neutral.", "quote": ""},
            {"item_id": "disclosure",            "result": "pass",           "explanation": "Fee disclosed.", "quote": "The Pro plan is $49/month"},
            {"item_id": "prohibited_promises",   "result": "pass",           "explanation": "No prohibited promises.", "quote": ""},
            {"item_id": "closure",               "result": "pass",           "explanation": "Agent thanked and offered help.", "quote": "Have a great day"},
        ],
        "expected_score": 100, "expected_coverage": 1.0, "expected_critical_violation": False,
    },
    # 2 - Critical: no identity check
    {
        "label": "Critical: no identity verification before disclosure",
        "fixture_type": "synthetic_fixture", "gold_status": "synthetic",
        "items": [
            {"item_id": "greeting",              "result": "pass",   "explanation": "", "quote": ""},
            {"item_id": "identity_verification", "result": "fail",   "explanation": "Disclosed balance without verifying.", "quote": "Your balance is $0"},
            {"item_id": "empathy",               "result": "not_applicable", "explanation": "", "quote": ""},
            {"item_id": "disclosure",            "result": "not_applicable", "explanation": "", "quote": ""},
            {"item_id": "prohibited_promises",   "result": "pass",   "explanation": "", "quote": ""},
            {"item_id": "closure",               "result": "pass",   "explanation": "", "quote": ""},
        ],
        "expected_score_max": 60, "expected_coverage": 1.0, "expected_critical_violation": True,
    },
    # 3 - Prohibited promise
    {
        "label": "Critical: prohibited promise on fix date",
        "fixture_type": "synthetic_fixture", "gold_status": "synthetic",
        "items": [
            {"item_id": "greeting",              "result": "pass",           "explanation": "", "quote": ""},
            {"item_id": "identity_verification", "result": "not_applicable", "explanation": "", "quote": ""},
            {"item_id": "empathy",               "result": "pass",           "explanation": "", "quote": ""},
            {"item_id": "disclosure",            "result": "not_applicable", "explanation": "", "quote": ""},
            {"item_id": "prohibited_promises",   "result": "fail",           "explanation": "Guaranteed fix date.", "quote": "I guarantee it will be fixed by tomorrow"},
            {"item_id": "closure",               "result": "fail",           "explanation": "No next steps.", "quote": ""},
        ],
        "expected_score_max": 60, "expected_coverage": 1.0, "expected_critical_violation": True,
    },
    # 4 - Needs review on disclosure
    {
        "label": "Needs review: disclosure ambiguous (roaming fee)",
        "fixture_type": "synthetic_fixture", "gold_status": "synthetic",
        "items": [
            {"item_id": "greeting",              "result": "pass",         "explanation": "", "quote": ""},
            {"item_id": "identity_verification", "result": "not_applicable","explanation": "", "quote": ""},
            {"item_id": "empathy",               "result": "not_applicable","explanation": "", "quote": ""},
            {"item_id": "disclosure",            "result": "needs_review", "explanation": "Roaming charges not stated.", "quote": ""},
            {"item_id": "prohibited_promises",   "result": "pass",         "explanation": "", "quote": ""},
            {"item_id": "closure",               "result": "fail",         "explanation": "No summary.", "quote": ""},
        ],
        "expected_coverage_lt": 1.0, "expected_critical_violation": False,
    },
    # 5 - Short general inquiry: most items N/A
    {
        "label": "Short general inquiry: most items not applicable",
        "fixture_type": "synthetic_fixture", "gold_status": "synthetic",
        "items": [
            {"item_id": "greeting",              "result": "pass",           "explanation": "", "quote": ""},
            {"item_id": "identity_verification", "result": "not_applicable", "explanation": "", "quote": ""},
            {"item_id": "empathy",               "result": "not_applicable", "explanation": "", "quote": ""},
            {"item_id": "disclosure",            "result": "not_applicable", "explanation": "", "quote": ""},
            {"item_id": "prohibited_promises",   "result": "pass",           "explanation": "", "quote": ""},
            {"item_id": "closure",               "result": "pass",           "explanation": "", "quote": ""},
        ],
        "expected_score": 100, "expected_coverage": 1.0, "expected_critical_violation": False,
    },
    # 6 - Missing greeting only
    {
        "label": "Fail: missing greeting only",
        "fixture_type": "synthetic_fixture", "gold_status": "synthetic",
        "items": [
            {"item_id": "greeting",              "result": "fail",           "explanation": "No name or company in opening.", "quote": ""},
            {"item_id": "identity_verification", "result": "not_applicable", "explanation": "", "quote": ""},
            {"item_id": "empathy",               "result": "not_applicable", "explanation": "", "quote": ""},
            {"item_id": "disclosure",            "result": "not_applicable", "explanation": "", "quote": ""},
            {"item_id": "prohibited_promises",   "result": "pass",           "explanation": "", "quote": ""},
            {"item_id": "closure",               "result": "pass",           "explanation": "", "quote": ""},
        ],
        "expected_critical_violation": False,
    },
    # 7 - Empathy fail with frustrated customer
    {
        "label": "Fail: empathy missing when customer frustrated",
        "fixture_type": "synthetic_fixture", "gold_status": "synthetic",
        "items": [
            {"item_id": "greeting",              "result": "pass", "explanation": "", "quote": ""},
            {"item_id": "identity_verification", "result": "pass", "explanation": "", "quote": ""},
            {"item_id": "empathy",               "result": "fail", "explanation": "No acknowledgment of frustration.", "quote": ""},
            {"item_id": "disclosure",            "result": "not_applicable", "explanation": "", "quote": ""},
            {"item_id": "prohibited_promises",   "result": "pass", "explanation": "", "quote": ""},
            {"item_id": "closure",               "result": "pass", "explanation": "", "quote": ""},
        ],
        "expected_critical_violation": False,
    },
    # 8 - Disclosure fail on technician fee
    {
        "label": "Critical: disclosure fail on technician visit fee",
        "fixture_type": "synthetic_fixture", "gold_status": "synthetic",
        "items": [
            {"item_id": "greeting",              "result": "pass", "explanation": "", "quote": ""},
            {"item_id": "identity_verification", "result": "pass", "explanation": "", "quote": ""},
            {"item_id": "empathy",               "result": "pass", "explanation": "", "quote": ""},
            {"item_id": "disclosure",            "result": "fail", "explanation": "No callout fee disclosed before booking.", "quote": ""},
            {"item_id": "prohibited_promises",   "result": "pass", "explanation": "", "quote": ""},
            {"item_id": "closure",               "result": "pass", "explanation": "", "quote": ""},
        ],
        "expected_critical_violation": True, "expected_score_max": 60,
    },
    # 9 - All items fail
    {
        "label": "All items fail",
        "fixture_type": "synthetic_fixture", "gold_status": "synthetic",
        "items": [
            {"item_id": "greeting",              "result": "fail", "explanation": "", "quote": ""},
            {"item_id": "identity_verification", "result": "fail", "explanation": "", "quote": ""},
            {"item_id": "empathy",               "result": "fail", "explanation": "", "quote": ""},
            {"item_id": "disclosure",            "result": "fail", "explanation": "", "quote": ""},
            {"item_id": "prohibited_promises",   "result": "fail", "explanation": "", "quote": ""},
            {"item_id": "closure",               "result": "fail", "explanation": "", "quote": ""},
        ],
        "expected_score": 0, "expected_critical_violation": True,
    },
    # 10 - All needs_review
    {
        "label": "All items needs_review",
        "fixture_type": "synthetic_fixture", "gold_status": "synthetic",
        "items": [
            {"item_id": "greeting",              "result": "needs_review", "explanation": "", "quote": ""},
            {"item_id": "identity_verification", "result": "needs_review", "explanation": "", "quote": ""},
            {"item_id": "empathy",               "result": "needs_review", "explanation": "", "quote": ""},
            {"item_id": "disclosure",            "result": "needs_review", "explanation": "", "quote": ""},
            {"item_id": "prohibited_promises",   "result": "needs_review", "explanation": "", "quote": ""},
            {"item_id": "closure",               "result": "needs_review", "explanation": "", "quote": ""},
        ],
        "expected_score": 0, "expected_coverage_lt": 1.0, "expected_critical_violation": False,
    },
    # 11-30: parametrized combo fixtures
    *[
        {
            "label": f"Combo fixture {n}",
            "fixture_type": "synthetic_fixture", "gold_status": "synthetic",
            "items": [
                {"item_id": "greeting",              "result": "pass" if n % 2 == 0 else "fail",              "explanation": "", "quote": ""},
                {"item_id": "identity_verification", "result": "not_applicable" if n % 3 == 0 else "pass",    "explanation": "", "quote": ""},
                {"item_id": "empathy",               "result": "not_applicable",                               "explanation": "", "quote": ""},
                {"item_id": "disclosure",            "result": "pass" if n % 4 != 0 else "not_applicable",    "explanation": "", "quote": ""},
                {"item_id": "prohibited_promises",   "result": "pass",                                         "explanation": "", "quote": ""},
                {"item_id": "closure",               "result": "pass" if n % 5 != 0 else "fail",              "explanation": "", "quote": ""},
            ],
            "expected_critical_violation": False,
        }
        for n in range(11, 31)
    ],
]

assert len(FIXTURES) == 30, f"Expected 30 fixtures, got {len(FIXTURES)}"
