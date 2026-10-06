"""
Shared pytest fixtures for unit and integration tests.
"""
from __future__ import annotations

import os

import httpx
import pytest
import pytest_asyncio

from backend.auth import hash_password
from backend.config.settings import get_settings
from backend.db import close_db, create_all_tables, get_db_session, init_db
from backend.models import User


@pytest.fixture(scope="session", autouse=True)
def _env_defaults():
    """Set baseline env vars once for the whole test session."""
    os.environ.setdefault("GROQ_API_KEY", "gsk_test_placeholder")
    os.environ.setdefault("SECRET_KEY", "a" * 64)
    os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    os.environ.setdefault("APP_ENV", "test")
    os.environ.setdefault("LOG_LEVEL", "WARNING")


@pytest.fixture
def env(monkeypatch):
    """Per-test env override that clears settings cache."""
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    monkeypatch.setenv("SECRET_KEY", "a" * 64)
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    monkeypatch.setenv("SEED_USERS", "admin:pass:admin")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
    from backend import db as _db
    _db._engine = None
    _db._session_factory = None


@pytest_asyncio.fixture
async def app_db(env):
    """Fresh in-memory DB + tables for each test."""
    s = get_settings()
    init_db(s.database_url)
    await create_all_tables()
    yield
    await close_db()


@pytest_asyncio.fixture
async def admin_client(env, app_db):
    """HTTPX async client with seeded admin user, ready to login."""
    async with get_db_session() as session:
        session.add(User(username="admin", password_hash=hash_password("pass"),
                         role="admin", is_active=True))
        await session.flush()

    from backend.api.main import create_app
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def get_token(client: httpx.AsyncClient, username="admin", password="pass") -> str:
    r = await client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest_asyncio.fixture
async def action_enabled_client(monkeypatch, env, app_db):
    """
    HTTPX async client with action layer enabled.
    Seeds admin user + act_settings via the app's own session.
    """
    monkeypatch.setenv("ACTION_LAYER_ENABLED", "true")

    from backend.api.main import create_app
    from backend.auth import hash_password as _hash
    from backend.db import create_all_tables as _create_tables
    from backend.db import get_db_session as _get_session

    app = create_app()
    # Ensure tables exist in this engine (create_app may have re-initialised the engine)
    await _create_tables()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        async with _get_session() as session:
            from backend.action_layer.models import ActSettings as _ActSettings
            from backend.models import User as _User
            session.add(_User(username="admin", password_hash=_hash("pass"),
                              role="admin", is_active=True))
            session.add(_ActSettings(enabled=True))
            await session.flush()
        yield c

