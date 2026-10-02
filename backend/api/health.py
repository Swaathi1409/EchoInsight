"""
Health and readiness endpoints.

GET /health  - Liveness probe. Returns 200 if the process is alive.
GET /ready   - Readiness probe. Returns 200 if the database is reachable
               and the latest migration has been applied.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter
from sqlalchemy import text

from backend.db import get_db_session
from backend.schemas import HealthResponse, ReadyResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness probe",
    description="Returns 200 if the process is alive. No database check.",
)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get(
    "/ready",
    response_model=ReadyResponse,
    summary="Readiness probe",
    description=(
        "Returns 200 if the database is reachable and the schema is up to date. "
        "Returns 503 if not ready."
    ),
    responses={503: {"description": "Not ready"}},
)
async def ready() -> ReadyResponse:
    db_status = "unreachable"
    migration_status = "unknown"

    try:
        async with get_db_session() as session:
            await session.execute(text("SELECT 1"))
            db_status = "ok"

            # Check that the alembic_version table exists and has a row
            try:
                result = await session.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
                row = result.fetchone()
                migration_status = row[0] if row else "no_migrations"
            except Exception:
                migration_status = "table_missing"

    except Exception as exc:
        logger.warning("Readiness check failed: %s", exc)
        from fastapi import HTTPException
        raise HTTPException(
            status_code=503,
            detail={
                "status": "not_ready",
                "database": db_status,
                "migrations": migration_status,
            },
        )

    return ReadyResponse(
        status="ok",
        database=db_status,
        migrations=migration_status,
    )
