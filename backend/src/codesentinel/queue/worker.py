"""Review queue worker — polls Postgres for jobs with bounded concurrency.

Uses SELECT ... FOR UPDATE SKIP LOCKED for safe concurrent claiming
across multiple worker replicas. Retries with exponential backoff
on throttle errors. Dead letters after max attempts.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text, select
from structlog import get_logger

from codesentinel.config.settings import get_settings
from codesentinel.database.models import ReviewJob, utcnow
from codesentinel.database.session import async_session_factory, engine
from codesentinel.queue.processor import process_review_job

logger = get_logger()
_settings = get_settings()

_worker_id = str(uuid.uuid4())[:8]


def _is_throttle_error(error: Exception) -> bool:
    """Check if an error is a rate-limiting / throttle error."""
    error_str = str(error).lower()
    return any(
        keyword in error_str
        for keyword in ["429", "rate limit", "too many requests", "throttl"]
    )


async def claim_jobs(concurrency: int) -> list[ReviewJob]:
    """Claim queued jobs using FOR UPDATE SKIP LOCKED."""
    lock_seconds = _settings.review_lock_seconds
    now = utcnow()

    async with async_session_factory() as session:
        result = await session.execute(
            text("""
                UPDATE review_jobs
                SET status = 'processing',
                    locked_at = :now,
                    locked_by = :worker_id,
                    attempts = attempts + 1,
                    updated_at = :now
                WHERE id IN (
                    SELECT id FROM review_jobs
                    WHERE status = 'queued'
                      AND next_attempt_at <= :now
                    ORDER BY created_at
                    LIMIT :limit
                    FOR UPDATE SKIP LOCKED
                )
                RETURNING *
            """),
            {
                "now": now,
                "worker_id": _worker_id,
                "limit": concurrency,
            },
        )
        rows = result.fetchall()
        jobs = []
        for row in rows:
            job = ReviewJob(
                id=row.id,
                installation_id=row.installation_id,
                repo_full_name=row.repo_full_name,
                pr_number=row.pr_number,
                commit_sha=row.commit_sha,
                payload=row.payload,
                status=row.status,
                attempts=row.attempts,
                locked_at=row.locked_at,
                locked_by=row.locked_by,
                next_attempt_at=row.next_attempt_at,
            )
            jobs.append(job)
        await session.commit()
        return jobs


async def complete_job(job_id: int) -> None:
    """Mark a job as done."""
    async with async_session_factory() as session:
        await session.execute(
            text(
                "UPDATE review_jobs SET status = 'done', updated_at = :now WHERE id = :id"
            ),
            {"now": utcnow(), "id": job_id},
        )
        await session.commit()


async def retry_job(job_id: int, error: str) -> None:
    """Re-queue a job for retry with exponential backoff."""
    backoff = _settings.review_backoff_base_seconds * (2 ** (1 - 1))
    next_attempt = utcnow() + timedelta(seconds=backoff)

    async with async_session_factory() as session:
        await session.execute(
            text("""
                UPDATE review_jobs
                SET status = 'queued',
                    next_attempt_at = :next,
                    error_message = :error,
                    locked_at = NULL,
                    locked_by = NULL,
                    updated_at = :now
                WHERE id = :id
            """),
            {
                "next": next_attempt,
                "error": error[:500],
                "now": utcnow(),
                "id": job_id,
            },
        )
        await session.commit()

    logger.info("job_retried", job_id=job_id, backoff_seconds=backoff)


async def kill_job(job_id: int, error: str) -> None:
    """Mark a job as dead (exhausted retries)."""
    async with async_session_factory() as session:
        await session.execute(
            text("""
                UPDATE review_jobs
                SET status = 'dead',
                    error_message = :error,
                    updated_at = :now
                WHERE id = :id
            """),
            {
                "error": error[:500],
                "now": utcnow(),
                "id": job_id,
            },
        )
        await session.commit()

    logger.warning("job_dead", job_id=job_id, error=error[:200])


async def _process_one(job: ReviewJob) -> None:
    """Process a single job with error handling."""
    try:
        await process_review_job(job)
        await complete_job(job.id)
    except Exception as e:
        error_str = str(e)
        logger.error("job_error", job_id=job.id, error=error_str)

        if _is_throttle_error(e) and job.attempts < _settings.review_max_attempts:
            await retry_job(job.id, error_str)
        elif job.attempts >= _settings.review_max_attempts:
            await kill_job(job.id, error_str)
        else:
            await kill_job(job.id, error_str)


async def start_worker() -> None:
    """Start the review queue worker loop."""
    concurrency = _settings.review_concurrency
    poll_interval = _settings.review_poll_interval_seconds

    logger.info(
        "review_worker_started",
        worker_id=_worker_id,
        concurrency=concurrency,
        poll_interval=poll_interval,
    )

    while True:
        try:
            jobs = await claim_jobs(concurrency)
            if jobs:
                logger.info("jobs_claimed", count=len(jobs))
                await asyncio.gather(*[_process_one(job) for job in jobs])
            await asyncio.sleep(poll_interval)
        except Exception as e:
            logger.error("worker_loop_error", error=str(e))
            await asyncio.sleep(poll_interval)
