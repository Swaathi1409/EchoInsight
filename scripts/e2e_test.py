"""
EchoInsight - Complete E2E Test Suite
Tests all implemented features with real API calls.
Run:  python scripts/e2e_test.py
NOTE: Run uvicorn WITHOUT --reload to avoid connection resets during tests.
      uvicorn backend.api.main:app
"""
import asyncio, httpx, sys

BASE = "http://localhost:8000"

results = []

def check(label, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    suffix = f" - {detail}" if detail else ""
    print(f"  [{status}] {label}{suffix}")
    results.append((label, condition))

async def req(client, method, url, **kwargs):
    """Retry wrapper: handles brief uvicorn reload gaps."""
    for attempt in range(3):
        try:
            return await getattr(client, method)(url, **kwargs)
        except (httpx.ReadError, httpx.ConnectError):
            if attempt == 2:
                raise
            await asyncio.sleep(3)

async def run(client, tok):
    h = {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}

    # 1. HEALTH
    print("\n[1] Health & Readiness")
    r = await req(client, "get", f"{BASE}/health")
    check("GET /health -> 200", r.status_code == 200)
    r = await req(client, "get", f"{BASE}/ready")
    data = r.json()
    check("GET /ready -> database ok", data.get("database") == "ok")

    # 2. AUTH
    print("\n[2] Auth")
    r = await req(client, "post", f"{BASE}/api/v1/auth/login",
        json={"username": "admin", "password": "admin123"})
    check("Login admin -> 200", r.status_code == 200)
    r = await req(client, "post", f"{BASE}/api/v1/auth/login",
        json={"username": "admin", "password": "wrongpass"})
    check("Wrong password -> 401", r.status_code == 401)

    # 3. CONVERSATIONS
    print("\n[3] Conversations")
    r = await req(client, "get", f"{BASE}/api/v1/conversations", headers=h)
    check("List conversations -> 200", r.status_code == 200)
    convs = r.json() if isinstance(r.json(), list) else []
    check("Has seeded conversations", len(convs) > 0, f"found {len(convs)}")

    # 4. CREATE -> TURNS -> END
    print("\n[4] Scenario: Billing Dispute (create -> turns -> end)")
    r = await req(client, "post", f"{BASE}/api/v1/conversations",
        json={"channel": "call", "source_id": "e2e-test-billing"}, headers=h)
    check("Create conversation -> 200/201", r.status_code in (200, 201))
    conv_id = r.json()["id"] if r.status_code in (200, 201) else None

    if conv_id:
        turns = [
            ("agent",    "Thank you for calling, my name is Alex. How can I help?"),
            ("customer", "Hi Alex, I was double charged. My account is 98765432."),
            ("agent",    "I can see the duplicate charge. Refund processed immediately."),
            ("customer", "My date of birth is 15th March 1985."),
            ("agent",    "Confirmed. Refund of 29.99 done. Reference: REF-12345."),
            ("customer", "Thank you so much!"),
            ("agent",    "Is there anything else I can help with today?"),
            ("customer", "No, that is great. Goodbye."),
        ]
        last_r = None
        for i, (sp, txt) in enumerate(turns):
            last_r = await req(client, "post", f"{BASE}/api/v1/conversations/{conv_id}/turns",
                json={"speaker": sp, "text": txt, "idempotency_key": f"e2e-{conv_id}-{i}"},
                headers=h, timeout=20)
        check("All 8 turns appended", last_r and last_r.status_code in (200, 201))

        # Verify redaction
        r = await req(client, "get", f"{BASE}/api/v1/conversations/{conv_id}", headers=h)
        conv_data = r.json()
        agent_turns = [t for t in conv_data.get("turns", []) if t["speaker"] == "agent"]
        alex_visible = any("Alex" in t["text_redacted"] for t in agent_turns)
        check("Agent name NOT redacted (Alex visible)", alex_visible)
        cust_turns = [t for t in conv_data.get("turns", []) if t["speaker"] == "customer"]
        acct_redacted = any("[ACCOUNT]" in t["text_redacted"] for t in cust_turns)
        check("Customer account number redacted", acct_redacted)

        # End (idempotent)
        r = await req(client, "post", f"{BASE}/api/v1/conversations/{conv_id}/end", headers=h)
        check("End conversation -> 200/202", r.status_code in (200, 202))
        job_id = r.json().get("job_id")
        check("Analysis job_id returned", job_id is not None)
        # Re-end must not crash
        r2 = await req(client, "post", f"{BASE}/api/v1/conversations/{conv_id}/end", headers=h)
        check("Re-end idempotent -> 200/202", r2.status_code in (200, 202))
        # Reopen
        r = await req(client, "post", f"{BASE}/api/v1/conversations/{conv_id}/reopen", headers=h)
        check("Reopen -> 200", r.status_code in (200, 201))
        await req(client, "post", f"{BASE}/api/v1/conversations/{conv_id}/end", headers=h)

    # 5. SUBMIT TRANSCRIPT
    print("\n[5] Scenario: Submit full transcript (batch ingest)")
    transcript_turns = [
        {"speaker": "agent",    "text": "Hello, support, I am Emma.", "idempotency_key": "sub-0"},
        {"speaker": "customer", "text": "My internet is down. Account 55443322.", "idempotency_key": "sub-1"},
        {"speaker": "agent",    "text": "Local outage in your area. Fixed by 6pm.", "idempotency_key": "sub-2"},
        {"speaker": "customer", "text": "I want compensation.", "idempotency_key": "sub-3"},
        {"speaker": "agent",    "text": "I will apply a credit to your account.", "idempotency_key": "sub-4"},
        {"speaker": "customer", "text": "Okay, thank you.", "idempotency_key": "sub-5"},
    ]
    r = await req(client, "post", f"{BASE}/api/v1/conversations/submit",
        json={"turns": transcript_turns, "channel": "call", "source_id": "e2e-submit-002"},
        headers=h, timeout=30)
    check("Submit transcript -> 200/202", r.status_code in (200, 201, 202))
    submit_conv_id = r.json().get("conversation_id") if r.status_code in (200, 201, 202) else None
    check("Got conversation_id", submit_conv_id is not None)
    # Idempotency
    r2 = await req(client, "post", f"{BASE}/api/v1/conversations/submit",
        json={"turns": transcript_turns, "channel": "call", "source_id": "e2e-submit-002"},
        headers=h, timeout=30)
    check("Duplicate source_id idempotent", r2.status_code in (200, 201, 202, 409))

    # 6. ANALYSIS
    print("\n[6] Analysis")
    ended_convs = [c for c in convs if c.get("status") == "ended"]
    if ended_convs:
        test_conv = ended_convs[0]["id"]
        r = await req(client, "get", f"{BASE}/api/v1/conversations/{test_conv}/analysis", headers=h)
        has_analysis = r.status_code == 200 and r.json().get("resolution")
        if has_analysis:
            an = r.json()
            check("Analysis has resolution", an.get("resolution") in
                  ("resolved","unresolved","escalated","partially_resolved","unknown","pending"))
            check("Analysis has churn_risk", an.get("churn_risk") in ("low","medium","high"))
            check("Analysis has summary", bool(an.get("summary")))
        else:
            check("Analysis available (may still process)", r.status_code in (200, 202),
                  f"HTTP {r.status_code}")
        r = await req(client, "get", f"{BASE}/api/v1/conversations/{test_conv}/qa", headers=h)
        check("QA endpoint accessible", r.status_code in (200, 404))
        if r.status_code == 200:
            check("QA has score", r.json().get("score") is not None)
    else:
        print(f"  [SKIP] No ended conversations - analysis test skipped")

    # 7. ADMIN
    print("\n[7] Admin Endpoints")
    r = await req(client, "get", f"{BASE}/api/v1/audit-logs", headers=h)
    check("Audit logs -> 200", r.status_code == 200)
    r = await req(client, "get", f"{BASE}/api/v1/checklists", headers=h)
    check("Checklists -> 200", r.status_code == 200)
    r = await req(client, "get", f"{BASE}/api/v1/cases", headers=h)
    check("Cases list -> 200", r.status_code == 200)
    r = await req(client, "get", f"{BASE}/budget-status", headers=h)
    check("Budget status -> 200", r.status_code == 200)
    check("Budget has used/limit fields", "used" in r.json() or "tokens_used_today" in r.json())

    # 8. CASES
    print("\n[8] Case Linking")
    create_r = await req(client, "post", f"{BASE}/api/v1/cases",
        json={"title": "E2E Test Case", "conversation_ids": [conv_id] if conv_id else []},
        headers=h)
    check("Create case -> 200/201", create_r.status_code in (200, 201))
    if create_r.status_code in (200, 201):
        cdata = create_r.json()
        case_id = cdata.get("case_id") or cdata.get("id")
        if case_id:
            r2 = await req(client, "get", f"{BASE}/api/v1/cases/{case_id}", headers=h)
            check("Get case by id -> 200", r2.status_code == 200)

    # 9. SECURITY
    print("\n[9] Security")
    r = await req(client, "get", f"{BASE}/api/v1/conversations")  # no token
    check("No token -> 401/403", r.status_code in (401, 403))
    r = await req(client, "get", f"{BASE}/api/v1/conversations",
        headers={"Authorization": "Bearer fake.token.here"})
    check("Fake token -> 401/403", r.status_code in (401, 403))

    # 10. REVIEWS
    print("\n[10] Reviewer Workflow")
    if conv_id:
        r = await req(client, "post", f"{BASE}/api/v1/conversations/{conv_id}/reviews",
            json={"verdict": "approved", "notes": "E2E test review"}, headers=h)
        check("Submit review -> 200/201", r.status_code in (200, 201))
        r = await req(client, "get", f"{BASE}/api/v1/conversations/{conv_id}/reviews", headers=h)
        check("Get reviews -> 200", r.status_code == 200)
        check("Review in history", len(r.json()) > 0 if r.status_code == 200 else False)

    # 11. ANALYSIS VERSIONS
    print("\n[11] Analysis Versions")
    if ended_convs:
        test_conv = ended_convs[0]["id"]
        r = await req(client, "get",
            f"{BASE}/api/v1/conversations/{test_conv}/analysis/versions", headers=h)
        check("Analysis versions endpoint -> 200", r.status_code == 200)

    # 12. SSE STREAM
    print("\n[12] SSE Stream")
    if conv_id:
        try:
            async with client.stream("GET",
                f"{BASE}/api/v1/conversations/{conv_id}/stream",
                headers=h, timeout=5) as resp:
                check("SSE stream connects -> 200", resp.status_code == 200)
                check("SSE content-type", "text/event-stream" in
                      resp.headers.get("content-type", ""))
        except Exception as e:
            check("SSE stream connects", False, str(e)[:60])

    # 13. REDACTOR UNIT CHECK
    print("\n[13] Redactor Logic")
    import sys as _sys; _sys.path.insert(0, '.')
    from backend.ingest.redactor import redact_turn
    agent_out = redact_turn("agent", "Thank you, my name is Sarah. How can I help?")
    check("Agent name NOT redacted", "Sarah" in agent_out, repr(agent_out[:60]))
    cust_out = redact_turn("customer", "My name is John Smith and my card is 4111111111111111")
    check("Customer name redacted", "John Smith" not in cust_out or "[NAME]" in cust_out)
    check("Customer card redacted", "[CARD]" in cust_out, repr(cust_out[:80]))


async def main():
    print("=" * 60)
    print("EchoInsight - Complete E2E Test Suite")
    print("=" * 60)

    async with httpx.AsyncClient(timeout=30) as client:
        r = await req(client, "post", f"{BASE}/api/v1/auth/login",
            json={"username": "admin", "password": "admin123"})
        if r.status_code != 200:
            print(f"\n[FATAL] Login failed: {r.status_code} {r.text[:100]}")
            print("Make sure: uvicorn is running + users are seeded")
            sys.exit(1)
        tok = r.json()["access_token"]
        print(f"Logged in as admin")
        await run(client, tok)

    total = len(results)
    passed = sum(1 for _, ok in results if ok)
    failed = total - passed
    print(f"\n{'='*60}")
    print(f"Results: {passed}/{total} passed", end="")
    if failed:
        print(f"  ({failed} FAILED)")
        for label, ok in results:
            if not ok:
                print(f"  FAILED: {label}")
    else:
        print(" - ALL PASSED")
    print("=" * 60)
    sys.exit(0 if failed == 0 else 1)

asyncio.run(main())
