"""Background worker: polls for queued jobs and runs them."""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy import select

from backend.config.settings import get_settings
from backend.db import get_db_session, init_db
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
        elif job.job_type == JobType.PER_TURN_EXTRACTION.value:
            # Per-turn extraction is handled inline in the append_turn API endpoint.
            # Mark as succeeded here to drain the queue without LLM calls.
            logger.debug("Per-turn extraction job %s: no-op (handled inline)", job.job_id[:8])
        else:
            logger.warning("Unknown job type: %s", job.job_type)


async def _process_one(job_id: str) -> None:
    async with get_db_session() as session:
        job = await session.get(Job, job_id)
        if job is None or job.status != JobStatus.QUEUED.value:
            return
        # Mark running
        job.status = JobStatus.RUNNING.value
        job.started_at = datetime.now(UTC)
        job.attempts += 1
        await session.flush()

    try:
        async with get_db_session() as session:
            job = await session.get(Job, job_id)
            await _run_job(job)

        async with get_db_session() as session:
            job = await session.get(Job, job_id)
            job.status = JobStatus.SUCCEEDED.value
            job.completed_at = datetime.now(UTC)
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
                job.completed_at = datetime.now(UTC)
                await session.flush()


async def poll_loop() -> None:
    logger.info("Worker started, polling every %ds", POLL_INTERVAL)
    import uuid
    from datetime import timedelta

    from backend.bootstrap import bootstrap_qa_checklists
    from backend.domain_model import ConversationStatus, JobType
    from backend.models import Conversation, Turn

    # Bootstrap QA Checklists on worker startup too
    async with get_db_session() as session:
        await bootstrap_qa_checklists(session)

    while True:
        try:
            async with get_db_session() as session:
                now = datetime.now(UTC)
                idle_threshold = now - timedelta(minutes=30)

                active_convs = (await session.execute(
                    select(Conversation).where(Conversation.status == ConversationStatus.ACTIVE.value)
                )).scalars().all()

                for conv in active_convs:
                    last_turn = (await session.execute(
                        select(Turn.timestamp).where(Turn.conversation_id == conv.id).order_by(Turn.seq.desc()).limit(1)
                    )).scalar_one_or_none()
                    # Use most recent activity: max of turn timestamp vs conv started_at
                    # This prevents immediately re-closing freshly reopened conversations
                    started_t = conv.started_at.replace(tzinfo=UTC) if conv.started_at and conv.started_at.tzinfo is None else (conv.started_at or now)
                    if last_turn:
                        last_t = last_turn.replace(tzinfo=UTC) if last_turn.tzinfo is None else last_turn
                        # Use whichever is more recent: last turn or when this session started
                        effective_last_active = max(last_t, started_t)
                        if effective_last_active < idle_threshold:
                            logger.info("Sweeping idle conversation %s", conv.id[:8])
                            conv.status = ConversationStatus.ENDED.value
                            conv.end_reason = "idle_timeout"
                            conv.ended_at = now
                            session.add(Job(
                                job_id=str(uuid.uuid4()),
                                job_type=JobType.FINAL_ANALYSIS.value,
                                status=JobStatus.QUEUED.value,
                                conversation_id=conv.id,
                                idempotency_key=f"final-idle-{conv.id}-{uuid.uuid4().hex[:8]}",
                            ))

                closed_threshold = now - timedelta(hours=72)
                ended_convs = (await session.execute(
                    select(Conversation).where(
                        Conversation.status == ConversationStatus.ENDED.value
                    )
                )).scalars().all()

                for conv in ended_convs:
                    if conv.ended_at:
                        ended_t = conv.ended_at.replace(tzinfo=UTC) if conv.ended_at.tzinfo is None else conv.ended_at
                        if ended_t < closed_threshold:
                            logger.info("Closing 72h expired conversation %s", conv.id[:8])
                            conv.status = ConversationStatus.CLOSED.value

                await session.flush()

            async with get_db_session() as session:
                result = await session.execute(
                    select(Job.job_id).where(Job.status == JobStatus.QUEUED.value)
                    .order_by(Job.created_at).limit(20)  # clear backlog fast
                )
                job_ids = [r[0] for r in result]

            for job_id in job_ids:
                await _process_one(job_id)
        except Exception as exc:
            logger.error("Worker poll error: %s", exc)

        await asyncio.sleep(POLL_INTERVAL)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    s = get_settings()
    init_db(s.database_url)
    asyncio.run(poll_loop())


if __name__ == "__main__":
    main()
