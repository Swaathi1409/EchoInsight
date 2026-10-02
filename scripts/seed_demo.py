"""
Full seed script: creates conversations covering every feature scenario.
Run with: python scripts/seed_demo.py

Creates:
  1. Billing dispute — RESOLVED (high QA score, commitment fulfilled)
  2. Network outage — UNRESOLVED (open commitment, churn risk HIGH)
  3. False resolution — FALSE_RESOLUTION flag triggered
  4. Escalation case — ESCALATED (supervisor referral)
  5. Active conversation — still in progress (live panel demo)
  6. A support Case linking convs 1+2
"""
import asyncio, sys, os, httpx, uuid, time

sys.path.insert(0, '.')
BASE = "http://localhost:8000"
CREDS = {"username": "admin", "password": "admin123"}


async def login(client):
    r = await client.post(f"{BASE}/api/v1/auth/login", json=CREDS)
    r.raise_for_status()
    return r.json()["access_token"]


def h(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


# ── Transcripts ──────────────────────────────────────────────────────────────

BILLING_RESOLVED = [
    ("agent",    "Thank you for calling TelecomCorp, my name is Sarah. How can I help you today?"),
    ("customer", "Hi Sarah, I've been charged twice for my monthly plan this month. I'm really frustrated."),
    ("agent",    "I completely understand your frustration and I sincerely apologise for this inconvenience. Can I please verify your account with your date of birth?"),
    ("customer", "Yes, it's the 12th of June 1990."),
    ("agent",    "Thank you. I can see your account clearly. You're right — there is a duplicate charge of £29.99 from the 1st and 3rd of this month. I'm going to raise an immediate refund for the duplicate amount."),
    ("customer", "How long will the refund take?"),
    ("agent",    "The refund will appear in your account within 3 to 5 business days. I'm processing it right now. Your reference number is REF-2024-88821."),
    ("customer", "Great, thank you. Is there anything else I should know?"),
    ("agent",    "The refund is now submitted. You'll also receive a confirmation email within the hour. Is there anything else I can help you with today?"),
    ("customer", "No, that's perfect. Thank you so much Sarah."),
    ("agent",    "You're very welcome. Thank you for calling TelecomCorp. Have a wonderful day!"),
]

NETWORK_UNRESOLVED = [
    ("agent",    "Thank you for calling TelecomCorp support, I'm James. How can I help?"),
    ("customer", "My internet has been down for 3 days now. This is completely unacceptable. I run a business from home."),
    ("agent",    "I'm very sorry to hear that. Can I please take your account number to look into this?"),
    ("customer", "It's ACC-5678923."),
    ("agent",    "Thank you. I can see there's a known outage in your area affecting our fibre network. Our engineers are working on it."),
    ("customer", "Three days! I've lost thousands of pounds in business. I want compensation and I'm seriously thinking about switching to another provider."),
    ("agent",    "I completely understand how serious this is for your business. I'm going to escalate this to our priority resolution team and arrange a callback from a senior engineer within 2 hours."),
    ("customer", "Two hours? It's been three days. I want to speak to a manager right now."),
    ("agent",    "I'm arranging that escalation right now. I'm also going to note your request for compensation which the team will assess. I'll create a priority ticket number TKT-99812 for you."),
    ("customer", "Fine. But if this isn't fixed by tonight I'm cancelling my contract."),
    ("agent",    "I understand. The escalation team will call you back within 2 hours. Is there anything else I can note for the team?"),
    ("customer", "Just fix it. That's all I ask."),
]

FALSE_RESOLUTION = [
    ("agent",    "Good morning, thank you for calling TelecomCorp. My name is David."),
    ("customer", "Hi, my bill is showing an extra charge for international calls but I never made any."),
    ("agent",    "Let me look into that for you. Can I confirm your postcode?"),
    ("customer", "SW1A 1AA."),
    ("agent",    "Thank you. I can see the charge. That looks like it's been applied correctly based on your plan."),
    ("customer", "But I never made any international calls! I don't even have the international calling add-on."),
    ("agent",    "I understand your concern. The charge seems to be from the 15th. Your account shows it was resolved last month."),
    ("customer", "No it wasn't! This is a new charge. Are you even looking at the right account?"),
    ("agent",    "Yes I can see your account. I believe this is now resolved on our end."),
    ("customer", "How is it resolved? You haven't done anything! You haven't even looked at the charge properly."),
    ("agent",    "I'll make a note and someone will follow up. Is there anything else?"),
    ("customer", "This is terrible service. I want to cancel my contract."),
]

ESCALATION = [
    ("agent",    "Thank you for calling TelecomCorp, this is Lisa speaking. How can I help?"),
    ("customer", "Hi Lisa, I need to discuss cancelling my contract. I've been a customer for 8 years but I'm fed up."),
    ("agent",    "I'm sorry to hear that. Can I ask what's prompted this?"),
    ("customer", "The speeds I'm getting are nowhere near what I'm paying for. I'm on a 1Gbps plan but I'm getting 50Mbps at best."),
    ("agent",    "I completely understand. That's a significant gap. Can I verify your account with your date of birth?"),
    ("customer", "14th March 1975."),
    ("agent",    "Thank you. I can see your account. I'm going to escalate this to our technical solutions team who specialise in speed issues. They can also discuss loyalty options given your 8 years with us."),
    ("customer", "I'm also interested in what retention offers you have. I've seen better deals for new customers."),
    ("agent",    "Absolutely. Our retention team have access to exclusive offers. I'm transferring you now — your case reference is CS-44123. Is there anything else before I transfer you?"),
    ("customer", "No, that's fine. Thank you Lisa."),
    ("agent",    "You're welcome. Thank you for your loyalty and I hope we can resolve this for you today."),
]

ACTIVE_TURNS = [
    ("agent",    "Thank you for calling TelecomCorp, my name is Alex. Can I take your name please?"),
    ("customer", "Yes, it's Emma Wilson."),
    ("agent",    "Thank you Emma. How can I help you today?"),
    ("customer", "I've just moved house and I need to transfer my broadband to my new address."),
    ("agent",    "Of course! I can help with that. Can I confirm your account number or the postcode on your account?"),
    ("customer", "Account number is ACC-1122334."),
]


async def submit_transcript(client, token, turns, source_id, channel="call"):
    payload = {
        "source_id": source_id,
        "channel": channel,
        "turns": [{"speaker": sp, "text": txt, "idempotency_key": f"{source_id}-{i}"} for i, (sp, txt) in enumerate(turns)],
    }
    r = await client.post(f"{BASE}/api/v1/conversations/submit", json=payload, headers=h(token), timeout=30)
    if r.status_code not in (200, 201, 202):
        print(f"  ERROR {r.status_code}: {r.text[:200]}")
        return None
    return r.json()


async def create_active(client, token):
    r = await client.post(f"{BASE}/api/v1/conversations", json={"channel": "call", "source_id": "demo-active-001"}, headers=h(token))
    r.raise_for_status()
    conv_id = r.json()["id"]
    for i, (sp, txt) in enumerate(ACTIVE_TURNS):
        await client.post(f"{BASE}/api/v1/conversations/{conv_id}/turns",
            json={"speaker": sp, "text": txt, "idempotency_key": f"active-{i}-{uuid.uuid4()}"},
            headers=h(token), timeout=30)
        await asyncio.sleep(0.3)
    return conv_id


async def create_case(client, token, title, conv_ids):
    r = await client.post(f"{BASE}/api/v1/cases",
        json={"title": title, "conversation_ids": conv_ids},
        headers=h(token))
    if r.status_code in (200, 201):
        return r.json().get("case_id")
    print(f"  Case create failed: {r.status_code} {r.text[:100]}")
    return None


async def main():
    print("=== EchoInsight Demo Seed ===\n")
    async with httpx.AsyncClient(timeout=60) as client:
        print("Logging in as admin...")
        tok = await login(client)
        print("OK\n")

        print("[1/5] Billing dispute (resolved)...")
        r1 = await submit_transcript(client, tok, BILLING_RESOLVED, "demo-billing-001")
        c1_id = r1["conversation_id"] if r1 else None
        print(f"  conversation_id: {c1_id}\n  job_id: {r1['job_id'] if r1 else 'FAILED'}")

        print("\n[2/5] Network outage (unresolved, high churn)...")
        r2 = await submit_transcript(client, tok, NETWORK_UNRESOLVED, "demo-network-001")
        c2_id = r2["conversation_id"] if r2 else None
        print(f"  conversation_id: {c2_id}")

        print("\n[3/5] False resolution case...")
        r3 = await submit_transcript(client, tok, FALSE_RESOLUTION, "demo-false-res-001")
        c3_id = r3["conversation_id"] if r3 else None
        print(f"  conversation_id: {c3_id}")

        print("\n[4/5] Escalation case...")
        r4 = await submit_transcript(client, tok, ESCALATION, "demo-escalation-001")
        c4_id = r4["conversation_id"] if r4 else None
        print(f"  conversation_id: {c4_id}")

        print("\n[5/5] Active conversation (live panel demo)...")
        c5_id = await create_active(client, tok)
        print(f"  conversation_id: {c5_id}")

        print("\n[6/6] Creating support case linking billing + network conversations...")
        linked = [x for x in [c1_id, c2_id] if x]
        case_id = await create_case(client, tok, "Customer Emma Wilson — Billing & Network Issues", linked)
        print(f"  case_id: {case_id}")

        print("\n=== SEED COMPLETE ===")
        print("\nAnalysis jobs are queued and will process in background (worker must be running).")
        print("Wait ~30 seconds, then refresh the dashboard to see all conversations.")
        print()
        print("Conversation IDs for UI testing:")
        ids = [("Billing resolved", c1_id), ("Network unresolved+churn", c2_id),
               ("False resolution", c3_id), ("Escalation", c4_id), ("Active/Live", c5_id)]
        for name, cid in ids:
            if cid:
                print(f"  {name}: http://localhost:3000/#/conversation/{cid}")

if __name__ == "__main__":
    asyncio.run(main())
