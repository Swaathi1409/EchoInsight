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

    yield

    await close_db()
    logger.info("Database engine closed. Shutdown complete.")


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

    # Request ID and security headers middleware
    @app.middleware("http")
    async def request_id_and_security_headers(request: Request, call_next):
        request_id = request.headers.get("X-Request-Id", str(uuid.uuid4()))
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        start = time.perf_counter()
        response: Response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 1)

        response.headers["X-Request-Id"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"

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
    app.include_router(auth_router)
    app.include_router(conv_router)
    app.include_router(analytics_router)

    return app


# Module-level app instance (used by uvicorn and tests)
app = create_app()
