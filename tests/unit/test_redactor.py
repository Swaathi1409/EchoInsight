"""Unit tests for PII redactor — no DB, no LLM."""
from backend.ingest.redactor import redact

# (text_input, must_not_contain, must_contain_tag)
CASES = [
    ("Call me at 555-123-4567 please.",          ["555-123-4567"],           ["[PHONE]"]),
    ("My number: +1 (800) 555-0199",             ["555-0199"],               ["[PHONE]"]),
    ("Email me at bob@example.com",              ["bob@example.com"],        ["[EMAIL]"]),
    ("Account 12345678 needs reset.",            ["12345678"],               ["[ACCOUNT]"]),
    ("Card ending in 4111111111111111.",         ["4111111111111111"],        ["[CARD]"]),
    ("SSN is 123-45-6789",                       ["123-45-6789"],            ["[NATIONAL_ID]"]),
    ("My name is John Smith.",                   [],                         []),  # name in isolation ok
    ("My name is John Smith, account 87654321",  ["87654321"],               ["[ACCOUNT]"]),
]


def test_phone_redacted():
    out = redact("Call me at 555-123-4567 please.")
    assert "555-123-4567" not in out
    assert "[PHONE]" in out


def test_email_redacted():
    out = redact("Email bob@example.com for support.")
    assert "bob@example.com" not in out
    assert "[EMAIL]" in out


def test_account_redacted():
    out = redact("Account 12345678 is overdue.")
    assert "12345678" not in out
    assert "[ACCOUNT]" in out


def test_card_redacted():
    out = redact("Card number 4111111111111111 is stored.")
    assert "4111111111111111" not in out
    assert "[CARD]" in out


def test_national_id_redacted():
    out = redact("SSN 123-45-6789 on file.")
    assert "123-45-6789" not in out
    assert "[NATIONAL_ID]" in out


def test_safe_text_unchanged():
    safe = "The customer wants to upgrade their plan."
    assert redact(safe) == safe


def test_multiple_pii_in_one_turn():
    text = "Phone: 800-555-1234. Email: alice@corp.io. Account 99887766."
    out = redact(text)
    assert "800-555-1234" not in out
    assert "alice@corp.io" not in out
    assert "99887766" not in out
    assert "[PHONE]" in out
    assert "[EMAIL]" in out
    assert "[ACCOUNT]" in out


def test_account_not_misclassified_as_phone():
    """8-digit account number must become [ACCOUNT], not [PHONE]."""
    out = redact("My account is 12345678.")
    assert "12345678" not in out
    assert "[ACCOUNT]" in out
    assert "[PHONE]" not in out


def test_idempotent_on_already_redacted():
    """Redacting already-redacted text should not corrupt it."""
    text = "Hi [PHONE], your account [ACCOUNT] is ready."
    assert redact(text) == text
