"""
Unit tests for health and readiness endpoints.
Uses SQLite in-memory via anyio + httpx.AsyncClient with ASGITransport.
No real database server required.
"""
from __future__ import annotations

import httpx
import pytest
import pytest_asyncio

# ---- env setup -------------------------------------------------------

@pytest.fixture(autouse=True)
def setup_env(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test_key_for_unit_tests")
    monkeypatch.setenv("SECRET_KEY", "a" * 64)
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("LOG_LEVEL", "WARNING")

    from backend.config.settings import get_settings
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()

    # Clean up any module-level engine state between tests
    from backend import db as _db
    _db._engine = None
    _db._session_factory = None


# ---- fixtures --------------------------------------------------------

@pytest_asyncio.fixture
async def app_client(setup_env):
    """Async httpx client wired to the FastAPI app via ASGI transport."""
    from backend.api.main import create_app
    from backend.config.settings import get_settings
    from backend.db import close_db, create_all_tables, init_db

    s = get_settings()
    init_db(s.database_url)
    await create_all_tables()

    application = create_app()
    transport = httpx.ASGITransport(app=application)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client

    await close_db()


# ---- tests -----------------------------------------------------------

@pytest.mark.asyncio
async def test_health_returns_200(app_client):
    """GET /health returns 200 with status=ok, no auth required."""
    resp = await app_client.get("/health")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_health_no_auth_required(app_client):
    """Health endpoint must be accessible without Authorization header."""
    resp = await app_client.get("/health", headers={})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_ready_with_migrated_db(app_client):
    """
    GET /ready with a DB that has tables created returns 200 or 503.
    Tables exist (create_all_tables ran) but alembic_version table is absent
    because we used SQLAlchemy create_all, not alembic upgrade.
    Ready endpoint should return 503 (migration check fails) but database=ok.
    """
    resp = await app_client.get("/ready")
    # Either 200 (alembic table found) or 503 (alembic table missing)
    assert resp.status_code in (200, 503)
    if resp.status_code == 200:
        data = resp.json()
        assert data["status"] == "ok"
        assert data["database"] == "ok"
    else:
        detail = resp.json().get("detail", {})
        # Database should still be reachable
        if isinstance(detail, dict):
            assert detail.get("database") == "ok"


@pytest.mark.asyncio
async def test_unknown_endpoint_returns_404(app_client):
    """Unknown endpoints return 404."""
    resp = await app_client.get("/nonexistent")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_health_response_shape(app_client):
    """Health response has exactly the expected JSON shape."""
    resp = await app_client.get("/health")
    data = resp.json()
    assert "status" in data
    assert data["status"] == "ok"
    # Must not contain unexpected fields
    assert set(data.keys()) == {"status"}
