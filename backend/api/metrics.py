"""
Prometheus metrics endpoint.
Exposes /metrics in Prometheus text format.
Tracks: request counts, error rates, LLM call stats, job queue depth, conversation counts.
"""
from __future__ import annotations
import time
from collections import defaultdict
from typing import Any

from fastapi import APIRouter, Response
from sqlalchemy import func, select, text

from backend.db import get_db_session
from backend.models import Conversation, Job, Analysis

router = APIRouter(tags=["metrics"])

# In-process counters (reset on restart; for production use prometheus_client or OTEL)
_counters: dict[str, int] = defaultdict(int)
_histograms: dict[str, list[float]] = defaultdict(list)
_start_time = time.time()


def increment(name: str, value: int = 1) -> None:
    _counters[name] += value


def observe(name: str, value: float) -> None:
    hist = _histograms[name]
    hist.append(value)
    if len(hist) > 10000:
        _histograms[name] = hist[-5000:]


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    idx = int(len(sorted_vals) * p / 100)
    return sorted_vals[min(idx, len(sorted_vals) - 1)]


def _format_prometheus(lines: list[str]) -> str:
    return "\n".join(lines) + "\n"


@router.get("/metrics", summary="Prometheus metrics")
async def metrics() -> Response:
    lines: list[str] = []
    uptime = time.time() - _start_time

    # Process uptime
    lines.append("# HELP echoinsight_uptime_seconds Process uptime in seconds")
    lines.append("# TYPE echoinsight_uptime_seconds gauge")
    lines.append(f"echoinsight_uptime_seconds {uptime:.2f}")

    # In-process counters
    for name, value in sorted(_counters.items()):
        safe = name.replace(".", "_").replace("-", "_")
        lines.append(f"# TYPE echoinsight_{safe} counter")
        lines.append(f"echoinsight_{safe} {value}")

    # Histogram p50/p95
    for name, values in sorted(_histograms.items()):
        safe = name.replace(".", "_").replace("-", "_")
        p50 = _percentile(values, 50)
        p95 = _percentile(values, 95)
        lines.append(f"# HELP echoinsight_{safe}_seconds Latency")
        lines.append(f"# TYPE echoinsight_{safe}_seconds summary")
        lines.append(f'echoinsight_{safe}_seconds{{quantile="0.5"}} {p50:.4f}')
        lines.append(f'echoinsight_{safe}_seconds{{quantile="0.95"}} {p95:.4f}')
        lines.append(f"echoinsight_{safe}_seconds_count {len(values)}")

    # DB-backed metrics
    try:
        async with get_db_session() as session:
            # Conversation counts by status
            rows = (await session.execute(
                select(Conversation.status, func.count(Conversation.id).label("n"))
                .group_by(Conversation.status)
            )).all()
            lines.append("# HELP echoinsight_conversations_total Conversations by status")
            lines.append("# TYPE echoinsight_conversations_total gauge")
            for row in rows:
                lines.append(f'echoinsight_conversations_total{{status="{row.status}"}} {row.n}')

            # Job queue depth by status
            job_rows = (await session.execute(
                select(Job.status, func.count(Job.job_id).label("n"))
                .group_by(Job.status)
            )).all()
            lines.append("# HELP echoinsight_jobs_total Jobs by status")
            lines.append("# TYPE echoinsight_jobs_total gauge")
            for row in job_rows:
                lines.append(f'echoinsight_jobs_total{{status="{row.status}"}} {row.n}')

            # Analysis count
            analysis_count = (await session.execute(
                select(func.count(Analysis.analysis_id))
            )).scalar_one()
            lines.append("# HELP echoinsight_analyses_total Total completed analyses")
            lines.append("# TYPE echoinsight_analyses_total gauge")
            lines.append(f"echoinsight_analyses_total {analysis_count}")

    except Exception as exc:
        lines.append(f"# DB metrics unavailable: {exc}")

    # Token budget
    try:
        from backend.llm.budget import get_budget_status
        from backend.config.settings import get_settings
        budget = get_budget_status(get_settings().llm_daily_token_budget)
        lines.append("# HELP echoinsight_token_budget_used Tokens used today")
        lines.append("# TYPE echoinsight_token_budget_used gauge")
        lines.append(f"echoinsight_token_budget_used {budget['used']}")
        lines.append("# HELP echoinsight_token_budget_limit Daily token budget limit")
        lines.append("# TYPE echoinsight_token_budget_limit gauge")
        lines.append(f"echoinsight_token_budget_limit {budget['limit']}")
    except Exception as exc:
        lines.append(f"# Budget metrics unavailable: {exc}")

    return Response(content=_format_prometheus(lines), media_type="text/plain; version=0.0.4")


@router.get("/budget-status", tags=["metrics"])
async def budget_status() -> dict:
    """JSON endpoint showing daily LLM token budget usage."""
    from backend.llm.budget import get_budget_status
    from backend.config.settings import get_settings
    return get_budget_status(get_settings().llm_daily_token_budget)
