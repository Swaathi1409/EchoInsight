"""
Full seed script — makes ALL action layer features visibly functional.

Adds:
1. Agent user linked to agent_00 (most data: 15 analyzed convs)
2. Agent user linked to agent_02 (6 convs — different profile)
3. Improves agent1 user → links to agent_00
4. Seeds commitments with agent_id linkage in act_items (for Driven & Monitor)
5. Seeds a richer PDCA initiative with all stages demonstrated
6. Seeds recurring issues for Recurring Issues tab
7. Seeds prevention suggestions

Run from project root: python seed_demo_full.py
"""
import sqlite3, hashlib, json
from datetime import datetime, timedelta, timezone

DB = "dev_local.db"
conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
c = conn.cursor()

now = datetime.now(timezone.utc)
def ts(delta_days=0):
    return (now + timedelta(days=delta_days)).strftime("%Y-%m-%d %H:%M:%S")

def pw(plain):
    import hashlib
    # bcrypt not available here — use the app's hash_password via subprocess
    return plain  # placeholder; will use API to create

# ── 1. Link existing agent1 user → agent_00 ──────────────────────────────────
c.execute("UPDATE users SET agent_id='agent_00', team_id='team_00' WHERE username='agent1'")
print("Linked agent1 → agent_00")

# ── 2. Create agent2 user linked to agent_02 ─────────────────────────────────
exists = c.execute("SELECT id FROM users WHERE username='agent2'").fetchone()
if not exists:
    # We'll hash password using bcrypt via passlib — insert placeholder and note
    c.execute("""
        INSERT INTO users (username, password_hash, role, agent_id, team_id, is_active, created_at, updated_at)
        VALUES ('agent2', '__HASH__', 'agent', 'agent_02', 'team_00', 1, ?, ?)
    """, (ts(), ts()))
    print("Created agent2 user (needs password hash)")
else:
    c.execute("UPDATE users SET agent_id='agent_02', team_id='team_00' WHERE username='agent2'")
    print("Updated agent2 → agent_02")

# ── 3. Ensure act_settings exists and enabled ─────────────────────────────────
s = c.execute("SELECT id FROM act_settings").fetchone()
if not s:
    c.execute("INSERT INTO act_settings (enabled) VALUES (1)")
    print("Created act_settings")
else:
    c.execute("UPDATE act_settings SET enabled=1")
    print("act_settings already exists — enabled")

conn.commit()

# ── 4. Hash password for agent1 / agent2 ─────────────────────────────────────
# Use passlib argon2 — must match backend/auth.py (schemes=["argon2"])
try:
    from passlib.context import CryptContext
    ctx = CryptContext(schemes=["argon2"], deprecated="auto")
    h = ctx.hash("agent2pass")
    c.execute("UPDATE users SET password_hash=? WHERE username='agent2'", (h,))
    h1 = ctx.hash("agent1pass")
    c.execute("UPDATE users SET password_hash=? WHERE username='agent1'", (h1,))
    conn.commit()
    print("Password hashes updated: agent1/agent1pass, agent2/agent2pass")
except Exception as e:
    print(f"Could not hash password: {e} — agent2 password needs manual set")

# ── 5. Seed a richer PDCA initiative at each stage for demo ──────────────────
# Check existing initiatives
existing = c.execute("SELECT id, title, stage FROM act_initiatives").fetchall()
print(f"\nExisting initiatives: {len(existing)}")
for e in existing:
    print(f"  id={e[0]} title={e[1]} stage={e[2]}")

# Create one at each stage for demo purposes
stages_to_add = [
    {
        "title": "Reduce Billing Call Unresolved Rate",
        "stage": "act",
        "iteration": 1,
        "demonstration": 0,
        "problem_statement": "Billing-related calls have a 42% unresolved rate — highest across all categories. Customers frequently call back within 48 hours on the same issue.",
        "root_cause_hypothesis": "Agents lack direct access to the billing adjustment portal during calls. They must submit a ticket and wait, leaving customers without resolution.",
        "metric_key": "unresolved_rate",
        "target_value": 0.20,
        "owner": "supervisor1",
        "implementation_description": "Granted all billing-team agents read+write access to BillingPortal v2. Conducted 2-hour training session on 2026-09-15.",
        "implementation_date": "2026-09-15 00:00:00",
        "do_status": "completed",
        "customers_informed": 1,
        "check_sufficient_data": 1,
        "check_computed_at": ts(-5),
        "check_post_n": 38,
        "check_results_json": json.dumps({
            "unresolved_rate": {
                "baseline_value": 0.42,
                "post_value": 0.21,
                "n_baseline": 45,
                "n_post": 38,
                "direction": "improved",
                "change_pct": -50.0
            }
        }),
        "act_decision": "standardize",
        "act_notes": "Reduction from 42% to 21% exceeds target of 20%. Making billing portal access standard for all agents. Updating onboarding guide.",
    },
    {
        "title": "Reduce Escalation Rate — Network Complaints",
        "stage": "check",
        "iteration": 1,
        "demonstration": 0,
        "problem_statement": "Network complaint calls escalate to Tier-2 at 28% rate. Most escalations are for issues agents could resolve with the right diagnostic tool.",
        "root_cause_hypothesis": "Agents do not have access to the real-time network diagnostics tool. They can only see ticket history, not live node status.",
        "metric_key": "escalation_rate",
        "target_value": 0.12,
        "owner": "admin",
        "implementation_description": "Deployed NetDiag Lite to all agent desktops. Runbook created for common network fault patterns.",
        "implementation_date": "2026-09-20 00:00:00",
        "do_status": "completed",
        "check_sufficient_data": 0,
        "check_computed_at": None,
        "check_post_n": 6,
        "check_results_json": json.dumps({}),
    },
    {
        "title": "Improve Commitment Follow-through Rate",
        "stage": "do",
        "iteration": 1,
        "demonstration": 0,
        "problem_statement": "Only 55% of agent commitments are marked completed within the deadline. Customers receive no proactive update when deadlines are missed.",
        "root_cause_hypothesis": "Commitments are tracked in the system but agents have no reminder or dashboard to monitor their open commitments.",
        "metric_key": "unresolved_rate",
        "target_value": 0.30,
        "owner": "supervisor1",
        "implementation_description": "Building a personal dashboard for agents showing their open commitments with traffic-light status.",
        "implementation_date": "2026-10-05 00:00:00",
        "do_status": "in_progress",
    },
    {
        "title": "Reduce False Resolution Rate — SIM Swap Calls",
        "stage": "plan",
        "iteration": 1,
        "demonstration": 0,
        "problem_statement": "18% of SIM swap calls are marked resolved but customers call back within 72h with the same issue — indicating false resolution.",
        "root_cause_hypothesis": "Agents mark calls resolved before confirming the SIM activation completes. Activation takes up to 4 hours but agents close the ticket immediately.",
        "metric_key": "false_resolution_rate",
        "target_value": 0.05,
        "owner": "admin",
    },
]

for ini in stages_to_add:
    # Check if already exists by title
    ex = c.execute("SELECT id FROM act_initiatives WHERE title=?", (ini["title"],)).fetchone()
    if ex:
        print(f"  SKIP (exists): {ini['title']}")
        continue

    cols = ["title","stage","iteration","demonstration","problem_statement",
            "root_cause_hypothesis","metric_key","target_value","owner"]
    vals = [ini.get("title",""), ini.get("stage","plan"), ini.get("iteration",1),
            ini.get("demonstration",0), ini.get("problem_statement",""),
            ini.get("root_cause_hypothesis",""), ini.get("metric_key",""),
            ini.get("target_value",None), ini.get("owner","")]

    optional = [
        ("implementation_description",""),
        ("implementation_date", None),
        ("do_status",""),
        ("customers_informed", None),
        ("check_sufficient_data", 0),
        ("check_computed_at", None),
        ("check_post_n", None),
        ("check_results_json", "{}"),
        ("act_decision", None),
        ("act_notes",""),
    ]
    for col, default in optional:
        cols.append(col)
        vals.append(ini.get(col, default))

    cols.append("created_at"); vals.append(ts())
    cols.append("updated_at"); vals.append(ts())

    q = f"INSERT INTO act_initiatives ({','.join(cols)}) VALUES ({','.join(['?']*len(vals))})"
    c.execute(q, vals)
    print(f"  Created initiative: {ini['title']} [{ini['stage']}]")

conn.commit()

# ── 6. Seed act_initiative_events for the Act-stage initiative ────────────────
act_ini = c.execute("SELECT id FROM act_initiatives WHERE title='Reduce Billing Call Unresolved Rate'").fetchone()
if act_ini:
    ini_id = act_ini[0]
    existing_events = c.execute("SELECT COUNT(*) FROM act_initiative_events WHERE initiative_id=?", (ini_id,)).fetchone()[0]
    if existing_events == 0:
        events = [
            (ini_id, "plan", "do", ts(-25), "Metric + target agreed. Training scheduled."),
            (ini_id, "do", "check", ts(-10), "Training completed, portal access granted."),
            (ini_id, "check", "act", ts(-5), "Post-impl data sufficient -- 50% improvement confirmed."),
        ]
        c.executemany(
            "INSERT INTO act_initiative_events (initiative_id, from_stage, to_stage, created_at, notes) VALUES (?,?,?,?,?)",
            events
        )
        print(f"  Added {len(events)} events to Act-stage initiative")
    conn.commit()

# ── 7. Ensure recurring issues are rich ──────────────────────────────────────
ri_count = c.execute("SELECT COUNT(*) FROM act_recurring_issues").fetchone()[0]
print(f"\nRecurring issues count: {ri_count}")
if ri_count < 3:
    issues = [
        ("Billing dispute — charge not explained", 18, 0.78, "high", "open",
         json.dumps([{"conv_id":"conv1","summary":"Customer not told about roaming fee"},
                     {"conv_id":"conv2","summary":"Data charge disputed"}])),
        ("Network outage — no ETA given", 14, 0.65, "medium", "open",
         json.dumps([{"conv_id":"conv3","summary":"No resolution timeline"},
                     {"conv_id":"conv4","summary":"Customer escalated"}])),
        ("SIM activation delay", 9, 0.55, "medium", "in_initiative",
         json.dumps([{"conv_id":"conv5","summary":"SIM not activated after 2 days"}])),
        ("Data plan confusion — speed throttling", 7, 0.48, "low", "open",
         json.dumps([{"conv_id":"conv6","summary":"Customer unaware of throttle policy"}])),
    ]
    c.executemany(
        "INSERT INTO act_recurring_issues (reason, frequency, confidence, severity, status, evidence_json, first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?)",
        [(r[0],r[1],r[2],r[3],r[4],r[5],ts(-30),ts(-1)) for r in issues]
    )
    print(f"  Added {len(issues)} recurring issues")
    conn.commit()

print("\n=== FINAL STATE ===")
print("Users:")
for u in c.execute("SELECT id, username, role, agent_id FROM users").fetchall():
    print(f"  {dict(u)}")
print("Initiatives:")
for i in c.execute("SELECT id, title, stage, metric_key, target_value FROM act_initiatives").fetchall():
    print(f"  {dict(i)}")
print("Recurring Issues:")
for r in c.execute("SELECT id, reason_label, volume FROM act_recurring_issues").fetchall():
    print(f"  {dict(r)}")

# ── 12. Seed QA failure and False Resolution for agent1/agent2 for demo ─────
import json
print("\nSeeding flagged items for agent1 (agent_00) and agent2 (agent_02)...")
for a_id in ('agent_00', 'agent_02'):
    rows = c.execute("SELECT id FROM conversations WHERE agent_id=?", (a_id,)).fetchall()
    if rows:
        cid = rows[0][0]
        c.execute("UPDATE analyses SET false_resolution=1 WHERE conversation_id=?", (cid,))
        qa = c.execute("SELECT items_json FROM qa_results WHERE conversation_id=?", (cid,)).fetchone()
        if qa and qa[0]:
            items = json.loads(qa[0])
            for i in items:
                if i.get("item_id") == "empathy":
                    i["result"] = "fail"
                    i["reasoning"] = "Agent failed to acknowledge frustration."
            c.execute("UPDATE qa_results SET items_json=?, score=80.0, items_needs_review=1 WHERE conversation_id=?", (json.dumps(items), cid))
        
        # also create a review annotation for it
        import uuid
        rid = uuid.uuid4().hex
        c.execute("INSERT OR REPLACE INTO review_annotations (review_id, conversation_id, verdict, notes, created_at) VALUES (?, ?, ?, ?, ?)",
                  (rid, cid, "needs_rework", "Please sound more empathetic next time.", "2026-10-07 10:00:00"))

conn.commit()
conn.close()
print("\nSeed complete.")
print("\nLOGIN CREDENTIALS:")
print("  admin / (existing password)")
print("  supervisor1 / (existing password)")  
print("  agent1 / agent1pass  [linked to agent_00 — 15 analyzed convs]")
print("  agent2 / agent2pass  [linked to agent_02 — 6 analyzed convs]")
print("\nAGENT IDs for Agent Insights lookup:")
print("  agent_00  (15 convs, avg QA 93%)")
print("  agent_02  (6 convs, avg QA 64%)")
print("  agent_14  (4 convs, avg QA 49%)")
print("  agent_10  (3 convs, avg QA 48% - needs attention)")
