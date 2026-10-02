"""
Async SQLAlchemy 2 engine and session factory.

Usage in FastAPI:
    from backend.db import get_db_session
    async with get_db_session() as session:
        ...

Or as a FastAPI dependency:
    from backend.db import db_session_dep
"""
from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.models import Base

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Return the module-level async engine. Must call init_db() first."""
    if _engine is None:
        raise RuntimeError("Database engine not initialized. Call init_db() first.")
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    if _session_factory is None:
        raise RuntimeError("Session factory not initialized. Call init_db() first.")
    return _session_factory


def init_db(database_url: str, echo: bool = False) -> None:
    """
    Initialize the async engine and session factory.
    Call once at application startup from the lifespan context manager.
    """
    global _engine, _session_factory

    connect_args: dict = {}
    if "sqlite" in database_url:
        connect_args = {"check_same_thread": False}

    _engine = create_async_engine(
        database_url,
        echo=echo,
        pool_pre_ping=True,
        connect_args=connect_args,
    )
    _session_factory = async_sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


async def create_all_tables() -> None:
    """Create all tables if they do not exist. For use in tests only."""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_all_tables() -> None:
    """Drop all tables. For use in tests only."""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def close_db() -> None:
    """Dispose the engine. Call at application shutdown."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Context manager yielding an async database session."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def _db_session_dependency() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a database session."""
    async with get_db_session() as session:
        yield session


# FastAPI typed dependency alias
DbSession = Annotated[AsyncSession, Depends(_db_session_dependency)]
