"""
Unit tests for the phrase matcher.
No LLM, no database. Pure deterministic logic.
"""
from backend.qa.phrase_matcher import (
    _is_negated,
    _normalize,
    check_closure,
    check_disclosure_trigger,
    check_greeting,
    check_identity_verification,
    check_prohibited_promises,
)


def _turns(*items):
    """Helper to build turn dicts."""
    return [{"turn_id": f"turn_{i:04d}", "speaker": sp, "text": txt}
            for i, (sp, txt) in enumerate(items, 1)]


class TestNormalize:
    def test_collapses_whitespace(self):
        assert _normalize("hello   world") == "hello world"

    def test_lowercases(self):
        assert _normalize("HELLO") == "hello"


class TestNegation:
    def test_detects_cannot(self):
        assert _is_negated("I cannot guarantee this", "guarantee")

    def test_detects_no(self):
        assert _is_negated("There is no promise of delivery", "promise")

    def test_not_negated_when_no_negation(self):
        assert not _is_negated("I guarantee this", "guarantee")


class TestGreeting:
    def test_detects_thank_you_for_calling(self):
        t = _turns(("agent", "Thank you for calling, my name is Sarah."))
        r = check_greeting(t)
        assert r.matched
        assert r.phrase == "thank you for calling"

    def test_detects_good_morning(self):
        t = _turns(("agent", "Good morning, how can I help you today?"))
        r = check_greeting(t)
        assert r.matched

    def test_no_greeting(self):
        t = _turns(("agent", "Your account shows a balance of 50."))
        r = check_greeting(t)
        assert not r.matched

    def test_only_checks_agent(self):
        # customer says thank you for calling — should not count
        t = _turns(("customer", "Thank you for calling me back."))
        r = check_greeting(t)
        assert not r.matched

    def test_only_checks_first_3_agent_turns(self):
        # greeting in 4th agent turn — should not count
        t = _turns(
            ("agent", "Hello."),
            ("customer", "Hi."),
            ("agent", "OK."),
            ("agent", "Let me check that."),
            ("agent", "Thank you for calling."),
        )
        # Only first 3 agent turns: Hello, OK, Let me check that
        r = check_greeting(t)
        assert not r.matched


class TestProhibitedPhrases:
    def test_guarantee_is_violation(self):
        t = _turns(("agent", "I guarantee this will be fixed by tomorrow."))
        r = check_prohibited_promises(t)
        assert r.matched
        assert r.phrase == "i guarantee"

    def test_can_guarantee_is_violation(self):
        t = _turns(("agent", "I can guarantee delivery within 24 hours."))
        r = check_prohibited_promises(t)
        assert r.matched

    def test_negated_guarantee_not_violation(self):
        # "cannot guarantee" should NOT be a violation
        t = _turns(("agent", "I cannot guarantee this will be resolved."))
        r = check_prohibited_promises(t)
        # negation detected → not matched
        assert not r.matched

    def test_no_violation_in_normal_speech(self):
        t = _turns(("agent", "I will check your account and update you shortly."))
        r = check_prohibited_promises(t)
        assert not r.matched

    def test_customer_promise_not_flagged(self):
        # customer says "i promise" — not agent
        t = _turns(("customer", "I promise I paid that bill."))
        r = check_prohibited_promises(t)
        assert not r.matched


class TestIdentityVerification:
    def test_date_of_birth(self):
        t = _turns(("agent", "Can I have your date of birth to verify your identity?"))
        r = check_identity_verification(t)
        assert r.matched

    def test_account_number(self):
        t = _turns(("agent", "Can you confirm your account number?"))
        r = check_identity_verification(t)
        assert r.matched

    def test_no_verification(self):
        t = _turns(("agent", "How can I help you today?"))
        r = check_identity_verification(t)
        assert not r.matched


class TestClosure:
    def test_is_there_anything_else(self):
        t = _turns(("agent", "Is there anything else I can help you with today?"))
        r = check_closure(t)
        assert r.matched

    def test_have_a_good_day(self):
        t = _turns(("agent", "Thank you for calling. Have a good day!"))
        r = check_closure(t)
        assert r.matched

    def test_no_closure(self):
        t = _turns(("agent", "Let me put you on hold for a moment."))
        r = check_closure(t)
        assert not r.matched

    def test_only_last_4_agent_turns(self):
        # closure in 1st turn of a long call — should NOT count (only last 4 checked)
        turns_data = [("agent", "Is there anything else I can help you with?")] + \
                     [("agent", "OK noted.")] * 5
        t = _turns(*turns_data)
        r = check_closure(t)
        # Last 4 agent turns are all "OK noted." — no closure phrase
        assert not r.matched


class TestDisclosureTrigger:
    def test_technician(self):
        t = _turns(("agent", "I can arrange for a technician to visit your premises."))
        r = check_disclosure_trigger(t)
        assert r.matched

    def test_dispatch(self):
        t = _turns(("agent", "We will dispatch an engineer to your location."))
        r = check_disclosure_trigger(t)
        assert r.matched
