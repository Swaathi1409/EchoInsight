"""
Additional CORE integration tests covering the master prompt test matrix:
- append-after-end returns 409
- idempotency replay (same key returns existing turn, no duplicate)
- single-speaker conversation (only agent turns)
- 150-turn call (stress)
- end twice returns 409
- GET conversation list (scope, pagination)
"""
from __future__ import annotations
import pytest
import pytest_asyncio
import httpx

from tests.integration.test_lifecycle import _login


@pytest.mark.asyncio
async def test_append_after_end_returns_409(admin_client):
    """Cannot append a turn to an ended conversation."""
    token = await _login(admin_client)
    h = {"Authorization": f"Bearer {token}"}

    r = await admin_client.post("/api/v1/conversations", json={"channel": "call"}, headers=h)
    assert r.status_code == 201
    conv_id = r.json()["id"]

    # End the conversation
    r2 = await admin_client.post(f"/api/v1/conversations/{conv_id}/end", json={}, headers=h)
    assert r2.status_code in (200, 202)

    # Attempt to append — must be 409
    r3 = await admin_client.post(
        f"/api/v1/conversations/{conv_id}/turns",
        json={"speaker": "agent", "text": "Late turn.", "idempotency_key": "late-k1"},
        headers=h,
    )
    assert r3.status_code == 409, f"Expected 409, got {r3.status_code}: {r3.text}"


@pytest.mark.asyncio
async def test_end_twice_returns_409(admin_client):
    """Calling /end on an already-ended conversation must return 409."""
    token = await _login(admin_client)
    h = {"Authorization": f"Bearer {token}"}

    r = await admin_client.post("/api/v1/conversations", json={"channel": "call"}, headers=h)
    conv_id = r.json()["id"]

    r2 = await admin_client.post(f"/api/v1/conversations/{conv_id}/end", json={}, headers=h)
    assert r2.status_code in (200, 202)

    r3 = await admin_client.post(f"/api/v1/conversations/{conv_id}/end", json={}, headers=h)
    assert r3.status_code == 409, f"Expected 409 on second end, got {r3.status_code}: {r3.text}"


@pytest.mark.asyncio
async def test_idempotency_replay(admin_client):
    """Posting the same idempotency_key twice returns the same turn_id, no duplicate stored."""
    token = await _login(admin_client)
    h = {"Authorization": f"Bearer {token}"}

    r = await admin_client.post("/api/v1/conversations", json={"channel": "call"}, headers=h)
    conv_id = r.json()["id"]

    payload = {"speaker": "agent", "text": "Hello, Union Mobile.", "idempotency_key": "idem-k1"}

    r1 = await admin_client.post(f"/api/v1/conversations/{conv_id}/turns", json=payload, headers=h)
    assert r1.status_code == 201
    first_turn_id = r1.json()["turn_id"]

    # Replay same key
    r2 = await admin_client.post(f"/api/v1/conversations/{conv_id}/turns", json=payload, headers=h)
    assert r2.status_code == 200  # 200 = idempotent replay (not 201 created)
    assert r2.json()["turn_id"] == first_turn_id, "Idempotency must return same turn_id"

    # Verify only 1 turn exists
    rd = await admin_client.get(f"/api/v1/conversations/{conv_id}", headers=h)
    assert rd.json()["turn_count"] == 1


@pytest.mark.asyncio
async def test_single_speaker_agent_only(admin_client):
    """Conversation with only agent turns must not error."""
    token = await _login(admin_client)
    h = {"Authorization": f"Bearer {token}"}

    r = await admin_client.post("/api/v1/conversations", json={"channel": "call"}, headers=h)
    conv_id = r.json()["id"]

    for i in range(3):
        rt = await admin_client.post(
            f"/api/v1/conversations/{conv_id}/turns",
            json={"speaker": "agent", "text": f"Agent message {i}.", "idempotency_key": f"agent-{i}"},
            headers=h,
        )
        assert rt.status_code == 201

    re = await admin_client.post(f"/api/v1/conversations/{conv_id}/end", json={}, headers=h)
    assert re.status_code in (200, 202)

    rd = await admin_client.get(f"/api/v1/conversations/{conv_id}", headers=h)
    assert rd.json()["turn_count"] == 3


@pytest.mark.asyncio
async def test_single_speaker_customer_only(admin_client):
    """Conversation with only customer turns must not error."""
    token = await _login(admin_client)
    h = {"Authorization": f"Bearer {token}"}

    r = await admin_client.post("/api/v1/conversations", json={"channel": "call"}, headers=h)
    conv_id = r.json()["id"]

    for i in range(2):
        rt = await admin_client.post(
            f"/api/v1/conversations/{conv_id}/turns",
            json={"speaker": "customer", "text": f"Customer message {i}.", "idempotency_key": f"cust-{i}"},
            headers=h,
        )
        assert rt.status_code == 201

    re = await admin_client.post(f"/api/v1/conversations/{conv_id}/end", json={}, headers=h)
    assert re.status_code in (200, 202)


@pytest.mark.asyncio
async def test_150_turn_call(admin_client):
    """150-turn call completes without error or timeout."""
    token = await _login(admin_client)
    h = {"Authorization": f"Bearer {token}"}

    r = await admin_client.post("/api/v1/conversations", json={"channel": "call"}, headers=h)
    conv_id = r.json()["id"]

    speakers = ["agent", "customer"]
    for i in range(150):
        speaker = speakers[i % 2]
        rt = await admin_client.post(
            f"/api/v1/conversations/{conv_id}/turns",
            json={
                "speaker": speaker,
                "text": f"Turn {i}: this is a test message for the {speaker}.",
                "idempotency_key": f"long-{i}",
            },
            headers=h,
        )
        assert rt.status_code == 201, f"Turn {i} failed: {rt.status_code}"

    re = await admin_client.post(f"/api/v1/conversations/{conv_id}/end", json={}, headers=h)
    assert re.status_code in (200, 202)

    rd = await admin_client.get(f"/api/v1/conversations/{conv_id}", headers=h)
    assert rd.json()["turn_count"] == 150


@pytest.mark.asyncio
async def test_list_conversations_pagination(admin_client):
    """List endpoint returns paginated results with correct limit/offset."""
    token = await _login(admin_client)
    h = {"Authorization": f"Bearer {token}"}

    # Create 3 conversations
    for _ in range(3):
        r = await admin_client.post("/api/v1/conversations", json={"channel": "call"}, headers=h)
        assert r.status_code == 201

    r_all = await admin_client.get("/api/v1/conversations?limit=2&offset=0", headers=h)
    assert r_all.status_code == 200
    body = r_all.json()
    assert len(body) <= 2


@pytest.mark.asyncio
async def test_get_nonexistent_conversation(admin_client):
    """GET on non-existent conversation ID must return 404."""
    token = await _login(admin_client)
    h = {"Authorization": f"Bearer {token}"}

    r = await admin_client.get("/api/v1/conversations/00000000-0000-0000-0000-000000000000", headers=h)
    assert r.status_code == 404
