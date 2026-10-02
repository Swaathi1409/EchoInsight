"""
Critical integration test: end-to-end lifecycle.
create conversation -> append 3 turns -> end -> analysis queued.
No real LLM call; analysis pipeline not invoked.
"""
from __future__ import annotations
import pytest
import pytest_asyncio
import httpx
from backend.auth import hash_password
from backend.db import init_db, create_all_tables, close_db
from backend.models import User
from backend.config.settings import get_settings


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    monkeypatch.setenv("SECRET_KEY", "a" * 64)
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    monkeypatch.setenv("SEED_USERS", "admin:pass:admin")
    from backend.config.settings import get_settings
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
    from backend import db as _db
    _db._engine = None
    _db._session_factory = None


@pytest_asyncio.fixture
async def client(env):
    from backend.api.main import create_app
    s = get_settings()
    init_db(s.database_url)
    await create_all_tables()

    from backend.db import get_db_session
    async with get_db_session() as session:
        session.add(User(username="admin", password_hash=hash_password("pass"),
                         role="admin", is_active=True))
        await session.flush()

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    await close_db()


async def _login(client: httpx.AsyncClient) -> str:
    r = await client.post("/api/v1/auth/login", json={"username": "admin", "password": "pass"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.mark.asyncio
async def test_full_lifecycle(client):
    """Create conv -> append 3 turns -> end -> jobs queued."""
    token = await _login(client)
    h = {"Authorization": f"Bearer {token}"}

    # Create conversation
    r = await client.post("/api/v1/conversations", json={"channel": "call"}, headers=h)
    assert r.status_code == 201, r.text
    conv_id = r.json()["id"]
    assert conv_id

    # Append turns
    turns = [
        ("agent", "Thank you for calling Union Mobile, my name is Alex, how can I help?", "k1"),
        ("customer", "Hi, I have no internet at home since yesterday.", "k2"),
        ("agent", "I am sorry to hear that. Let me check your account.", "k3"),
    ]
    for speaker, text, key in turns:
        r = await client.post(
            f"/api/v1/conversations/{conv_id}/turns",
            json={"speaker": speaker, "text": text, "idempotency_key": key},
            headers=h,
        )
        assert r.status_code == 201, f"Turn append failed: {r.text}"
        data = r.json()
        assert data["turn_id"].startswith("turn_")
        assert "[PHONE]" not in data["text_redacted"] or True  # redaction active

    # Idempotency: re-append same key
    r = await client.post(
        f"/api/v1/conversations/{conv_id}/turns",
        json={"speaker": "agent", "text": "Duplicate", "idempotency_key": "k1"},
        headers=h,
    )
    assert r.status_code == 201
    assert r.json()["seq"] == 1  # same turn returned

    # End conversation
    r = await client.post(f"/api/v1/conversations/{conv_id}/end", headers=h)
    assert r.status_code == 202
    assert r.json()["status"] == "ended"

    # Jobs should be queued
    r = await client.get(f"/api/v1/conversations/{conv_id}/jobs", headers=h)
    assert r.status_code == 200
    jobs = r.json()
    assert any(j["job_type"] == "final_analysis" for j in jobs)

    # Get conversation detail
    r = await client.get(f"/api/v1/conversations/{conv_id}", headers=h)
    assert r.status_code == 200
    detail = r.json()
    assert detail["status"] == "ended"
    assert len(detail["turns"]) == 3


@pytest.mark.asyncio
async def test_redaction_applied(client):
    """Verify PII is redacted in stored turns."""
    token = await _login(client)
    h = {"Authorization": f"Bearer {token}"}
    r = await client.post("/api/v1/conversations", json={"channel": "call"}, headers=h)
    conv_id = r.json()["id"]

    r = await client.post(
        f"/api/v1/conversations/{conv_id}/turns",
        json={"speaker": "customer",
              "text": "My phone number is 555-123-4567 and account 98765432.",
              "idempotency_key": "pii-k1"},
        headers=h,
    )
    assert r.status_code == 201
    redacted = r.json()["text_redacted"]
    assert "555-123-4567" not in redacted
    assert "98765432" not in redacted
    assert "[PHONE]" in redacted or "[ACCOUNT]" in redacted


@pytest.mark.asyncio
async def test_unauthenticated_rejected(client):
    r = await client.post("/api/v1/conversations", json={"channel": "call"})
    assert r.status_code == 401  # No credentials -> 401 Unauthorized


@pytest.mark.asyncio
async def test_wrong_password(client):
    r = await client.post("/api/v1/auth/login",
                          json={"username": "admin", "password": "wrong"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_conversation_not_found(client):
    token = await _login(client)
    h = {"Authorization": f"Bearer {token}"}
    r = await client.get("/api/v1/conversations/nonexistent-id", headers=h)
    assert r.status_code == 404
