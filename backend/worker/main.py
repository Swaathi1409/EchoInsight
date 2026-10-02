"""Background worker: polls for queued jobs and runs them."""
from __future__ import annotations
import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select, update

from backend.config.settings import get_settings
from backend.db import init_db, get_db_session
from backend.domain_model import JobStatus, JobType
from backend.models import Job

logger = logging.getLogger(__name__)
POLL_INTERVAL = 5  # seconds


async def _run_job(job: Job) -> None:
    from backend.analysis.pipeline import run_final_analysis
    async with get_db_session() as session:
        if job.job_type == JobType.FINAL_ANALYSIS.value:
            analysis_id = await run_final_analysis(job.conversation_id, session)
            logger.info("Final analysis complete: conv=%s analysis=%s", job.conversation_id[:8], analysis_id[:8])
        # PER_TURN_EXTRACTION jobs are lightweight; skipped in MVP worker
        # (handled synchronously in the append_turn route for demo)


async def _process_one(job_id: str) -> None:
    async with get_db_session() as session:
        job = await session.get(Job, job_id)
        if job is None or job.status != JobStatus.QUEUED.value:
            return
        # Mark running
        job.status = JobStatus.RUNNING.value
        job.started_at = datetime.now(timezone.utc)
        job.attempts += 1
        await session.flush()

    try:
        async with get_db_session() as session:
            job = await session.get(Job, job_id)
            await _run_job(job)

        async with get_db_session() as session:
            job = await session.get(Job, job_id)
            job.status = JobStatus.SUCCEEDED.value
            job.completed_at = datetime.now(timezone.utc)
            await session.flush()

    except Exception as exc:
        logger.exception("Job %s failed: %s", job_id[:8], exc)
        async with get_db_session() as session:
            job = await session.get(Job, job_id)
            if job:
                if job.attempts >= job.max_attempts:
                    job.status = JobStatus.FAILED.value
                else:
                    job.status = JobStatus.QUEUED.value
                job.error = str(exc)[:1000]
                job.completed_at = datetime.now(timezone.utc)
                await session.flush()


async def poll_loop() -> None:
    logger.info("Worker started, polling every %ds", POLL_INTERVAL)
    while True:
        try:
            async with get_db_session() as session:
                result = await session.execute(
                    select(Job.job_id).where(Job.status == JobStatus.QUEUED.value)
                    .order_by(Job.created_at).limit(5)
                )
                job_ids = [r[0] for r in result]

            for job_id in job_ids:
                await _process_one(job_id)
        except Exception as exc:
            logger.error("Worker poll error: %s", exc)

        await asyncio.sleep(POLL_INTERVAL)


def main() -> None:
    import os
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    s = get_settings()
    init_db(s.database_url)
    asyncio.run(poll_loop())


if __name__ == "__main__":
    main()
