"""
FastAPI application entry point.

Startup/shutdown lifecycle:
  - Initializes the DB engine and session factory
  - Closes the DB engine on shutdown

Middleware:
  - CORS with allow-list from settings
  - Request ID injection
  - Structured logging
  - Security headers
  - Prometheus metrics (if enabled)
"""
from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.api.health import router as health_router
from backend.config.settings import get_settings
from backend.db import close_db, init_db

logger = structlog.get_logger(__name__)


def _configure_logging(log_level: str) -> None:
    """Set up structlog for structured JSON logging in production, pretty in dev."""
    import sys

    settings = get_settings()
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    if settings.is_production:
        processors = shared_processors + [structlog.processors.JSONRenderer()]
    else:
        processors = shared_processors + [structlog.dev.ConsoleRenderer()]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(sys.stdout),
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, log_level.upper(), logging.INFO),
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: initialize resources on startup, release on shutdown."""
    settings = get_settings()
    _configure_logging(settings.log_level)

    logger.info(
        "EchoInsight starting",
        env=settings.app_env,
        primary_model=settings.llm_primary_model,
    )

    init_db(
        database_url=settings.database_url,
        echo=settings.is_development,
    )
    logger.info("Database engine initialized")

    # Auto-migrate: ensure all model columns exist (SQLite-safe ALTER TABLE)
    await _auto_migrate(settings.database_url)

    yield

    await close_db()
    logger.info("Database engine closed. Shutdown complete.")


async def _auto_migrate(database_url: str) -> None:
    """
    Lightweight schema sync for SQLite dev databases.
    Adds any missing columns from the ORM models using ALTER TABLE.
    Safe to run on every startup — no-ops if columns already exist.
    For Postgres, skips (use Alembic migrations instead).
    """
    if "sqlite" not in database_url:
        return  # Postgres: use Alembic
    from backend.db import get_engine
    from backend.models import Base
    import backend.action_layer.models  # noqa: F401 — registers act_* tables into Base.metadata
    from sqlalchemy import text, inspect
    engine = get_engine()
    async with engine.begin() as conn:
        # Ensure all tables exist
        await conn.run_sync(Base.metadata.create_all)
        # Check each table for missing columns
        def _sync_columns(sync_conn):
            inspector = inspect(sync_conn)
            for table in Base.metadata.sorted_tables:
                existing = {c["name"] for c in inspector.get_columns(table.name)}
                for col in table.columns:
                    if col.name not in existing:
                        col_type = col.type.compile(dialect=sync_conn.dialect)
                        nullable = "NULL" if col.nullable else "NOT NULL"
                        default = ""
                        if col.default is not None and col.default.is_scalar:
                            default = f" DEFAULT {col.default.arg!r}"
                        elif col.nullable:
                            default = " DEFAULT NULL"
                        ddl = f"ALTER TABLE {table.name} ADD COLUMN {col.name} {col_type}{default}"
                        try:
                            sync_conn.execute(text(ddl))
                            logger.info("Auto-migrate: added column", table=table.name, column=col.name)
                        except Exception as e:
                            logger.debug("Auto-migrate skip", table=table.name, column=col.name, reason=str(e))
        await conn.run_sync(_sync_columns)



def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="EchoInsight API",
        description=(
            "AI-powered conversation analytics for telecom contact centers. "
            "Analyzes call transcripts, produces QA scores with evidence, "
            "tracks commitments, and provides a real-time provisional view "
            "after every turn."
        ),
        version="0.1.0",
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Request-Id"],
        expose_headers=["X-Request-Id"],
    )

    # Request ID, security headers, and rate limiting middleware
    from collections import defaultdict
    _rate_window: dict = defaultdict(lambda: {"count": 0, "reset_at": 0.0})
    RATE_LIMIT = 200  # requests per minute per IP

    @app.middleware("http")
    async def request_id_and_security_headers(request: Request, call_next):
        request_id = request.headers.get("X-Request-Id", str(uuid.uuid4()))
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        # Rate limiting (skip for health/metrics)
        if settings.is_production and not request.url.path.startswith(("/health", "/ready", "/metrics")):
            ip = request.client.host if request.client else "unknown"
            now = time.time()
            window = _rate_window[ip]
            if now > window["reset_at"]:
                window["count"] = 0
                window["reset_at"] = now + 60
            window["count"] += 1
            if window["count"] > RATE_LIMIT:
                return JSONResponse(
                    status_code=429,
                    content={"code": "rate_limited", "message": "Too many requests"},
                    headers={"Retry-After": "60"},
                )

        start = time.perf_counter()
        response: Response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 1)

        response.headers["X-Request-Id"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        if settings.is_production:
            csp = (
                "default-src 'none'; "
                "script-src 'self'; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                "font-src 'self' https://fonts.gstatic.com; "
                "img-src 'self' data:; "
                "connect-src 'self'; "
                "frame-ancestors 'none';"
            )
            response.headers["Content-Security-Policy"] = csp

        logger.info(
            "request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=duration_ms,
        )
        return response

    # Prometheus metrics
    if settings.enable_metrics:
        try:
            from prometheus_client import make_asgi_app
            metrics_app = make_asgi_app()
            app.mount("/metrics", metrics_app)
        except ImportError:
            logger.warning("prometheus_client not installed; metrics endpoint disabled")

    # Global exception handler
    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = request.headers.get("X-Request-Id", "unknown")
        logger.exception("Unhandled exception", request_id=request_id, exc_info=exc)
        return JSONResponse(
            status_code=500,
            content={
                "code": "internal_error",
                "message": "An internal error occurred.",
                "request_id": request_id,
            },
        )

    # Routers
    app.include_router(health_router)

    from backend.api.auth import router as auth_router
    from backend.api.conversations import router as conv_router, analytics_router
    from backend.api.metrics import router as metrics_router
    from backend.api.admin import router as admin_router
    from backend.api.stream import router as stream_router
    from backend.api.cases import router as cases_router
    app.include_router(auth_router)
    app.include_router(conv_router)
    app.include_router(analytics_router)
    app.include_router(metrics_router)
    app.include_router(admin_router)
    app.include_router(stream_router)
    app.include_router(cases_router)

    # Action Intelligence Layer (additive, guarded by master switch)
    from backend.action_layer.api.router import router as action_router
    app.include_router(action_router, prefix="/api/v1")

    return app


# Module-level app instance (used by uvicorn and tests)
app = create_app()
